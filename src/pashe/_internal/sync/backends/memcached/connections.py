"""The connections of a sync backend to memcached: written by hand for each side, as asyncio and sockets differ."""

from __future__ import annotations

import socket
import threading
import time
from typing import TYPE_CHECKING, Final, final

from pashe._internal.memcached.protocol import Answer, read_header
from pashe.errors import BackendError

if TYPE_CHECKING:
    from collections.abc import Sequence

_CHUNK: Final = 65536  # bytes a read asks the socket for at most
_LINE_END: Final = b"\r\n"


@final
class MemcachedConnections:
    """Connections to one memcached, opened as calls need them and kept for the next ones.

    shortcut: no bound on how many are open, as many as threads call at once; add one if a service
    runs so many that memcached refuses connections.
    """

    __slots__ = ("_closed", "_host", "_idle", "_lock", "_port", "_timeout")

    def __init__(
        self,
        host: str,
        port: int,
        timeout: float,
    ) -> None:
        self._host = host
        self._port = port
        self._timeout = timeout
        self._idle: list[_Stream] = []
        self._lock = threading.Lock()  # over _idle and _closed: each connection serves one thread at a time
        self._closed = False

    def send(self, commands: Sequence[bytes]) -> list[Answer]:
        """Send commands at once and read an answer for each, in their order, within the timeout.

        The timeout bounds the whole call, as on the async side. A memcached that can't be reached,
        takes longer or fails a command raises BackendError; the connection of a call that raised
        is closed, as an answer may be left unread on it.
        """
        deadline = time.monotonic() + self._timeout
        stream = self._reusable() or self._open()
        try:
            stream.send(b"".join(commands), deadline)
            answers = [_read_answer(stream, deadline) for _ in commands]
        except BaseException as error:
            # a connection left in the middle of an answer would read it as the answer of the next call
            stream.close()
            if isinstance(error, OSError | EOFError):  # TimeoutError is an OSError
                msg = f"memcached: {error!r}"
                raise BackendError(msg) from error
            raise
        with self._lock:
            if not self._closed:
                self._idle.append(stream)
                return answers
        stream.close()  # a call that ran on as the backend closed keeps nothing open
        return answers

    def close(self) -> None:
        """Close every connection; one a call still holds closes as the call ends."""
        with self._lock:
            self._closed = True
            idle = self._idle
            self._idle = []
        for stream in idle:
            stream.close()

    def _reusable(self) -> _Stream | None:
        """An idle connection memcached still keeps open; one it closed, as on a restart, is dropped."""
        with self._lock:
            while self._idle:
                stream = self._idle.pop()
                if stream.is_idle():
                    return stream
                stream.close()
        return None

    def _open(self) -> _Stream:
        try:
            sock = socket.create_connection((self._host, self._port), timeout=self._timeout)
        except OSError as error:
            msg = f"memcached: can't connect to {self._host}:{self._port}: {error!r}"
            raise BackendError(msg) from error
        return _Stream(sock)


@final
class _Stream:
    """A socket and what it read past the last answer, each send and read bounded by one deadline."""

    __slots__ = ("_buffer", "_sock")

    def __init__(self, sock: socket.socket) -> None:
        self._sock = sock
        self._buffer = bytearray()

    def send(self, data: bytes, deadline: float) -> None:
        self._sock.settimeout(_left(deadline))
        self._sock.sendall(data)  # the timeout bounds sendall as a whole

    def read_line(self, deadline: float) -> bytes:
        """A line with its line end; EOFError if the connection closes before its end."""
        end = self._buffer.find(_LINE_END)
        while end == -1:
            self._fill(deadline)
            end = self._buffer.find(_LINE_END)
        return self._take(end + len(_LINE_END))

    def read_exactly(self, size: int, deadline: float) -> bytes:
        """Size bytes; EOFError if the connection closes before them."""
        while len(self._buffer) < size:
            self._fill(deadline)
        return self._take(size)

    def is_idle(self) -> bool:
        """Whether the socket is open with nothing to read: a closed one reads b"" at once, a desync reads bytes."""
        if self._buffer:
            return False
        self._sock.settimeout(0)
        try:
            self._sock.recv(1, socket.MSG_PEEK)
        except BlockingIOError:
            return True
        except OSError:
            return False
        return False

    def close(self) -> None:
        self._sock.close()

    def _fill(self, deadline: float) -> None:
        self._sock.settimeout(_left(deadline))
        chunk = self._sock.recv(_CHUNK)
        if not chunk:
            msg = "memcached: the connection closed in the middle of an answer"
            raise EOFError(msg)
        self._buffer += chunk

    def _take(self, size: int) -> bytes:
        taken = bytes(self._buffer[:size])
        self._buffer = self._buffer[size:]
        return taken


def _read_answer(stream: _Stream, deadline: float) -> Answer:
    answer, size = read_header(stream.read_line(deadline))
    if size is None:
        return answer
    data = stream.read_exactly(size + 2, deadline)  # the value and its \r\n
    return Answer(code=answer.code, flags=answer.flags, value=data[:-2])


def _left(deadline: float) -> float:
    """The seconds left until deadline: none left is a timeout, before the call waits at all."""
    left = deadline - time.monotonic()
    if left <= 0:
        msg = "memcached took longer than the timeout"
        raise TimeoutError(msg)
    return left

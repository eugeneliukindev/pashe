"""The connections of a sync backend to memcached: written by hand for each side, as asyncio and sockets differ."""

from __future__ import annotations

import socket
import threading
from typing import IO, TYPE_CHECKING, final

from pashe._internal.memcached.protocol import Answer, read_header
from pashe.errors import BackendError

if TYPE_CHECKING:
    from collections.abc import Sequence

    type _Connection = tuple[socket.socket, IO[bytes]]  # the socket, and the reader of its answers


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
        self._idle: list[_Connection] = []
        self._lock = threading.Lock()  # over _idle and _closed: each connection serves one thread at a time
        self._closed = False

    def send(self, commands: Sequence[bytes]) -> list[Answer]:
        """Send commands at once and read an answer for each, in their order, within the timeout.

        A memcached that can't be reached, takes longer or fails a command raises BackendError; the
        connection of a call that raised is closed, as an answer may be left unread on it.
        """
        sock, reader = self._reusable() or self._open()
        try:
            sock.sendall(b"".join(commands))  # the timeout of the socket bounds each send and read
            answers = [_read_answer(reader) for _ in commands]
        except BaseException as error:
            # a connection left in the middle of an answer would read it as the answer of the next call
            reader.close()
            sock.close()
            if isinstance(error, OSError | EOFError):  # TimeoutError is an OSError
                msg = f"memcached: {error!r}"
                raise BackendError(msg) from error
            raise
        with self._lock:
            if not self._closed:
                self._idle.append((sock, reader))
                return answers
        # a call that ran on as the backend closed keeps nothing open
        reader.close()
        sock.close()
        return answers

    def close(self) -> None:
        """Close every connection; one a call still holds closes as the call ends."""
        with self._lock:
            self._closed = True
            idle = self._idle
            self._idle = []
        for sock, reader in idle:
            reader.close()
            sock.close()

    def _reusable(self) -> _Connection | None:
        """An idle connection memcached still keeps open; one it closed, as on a restart, is dropped."""
        with self._lock:
            while self._idle:
                sock, reader = self._idle.pop()
                if _is_idle(sock, self._timeout):
                    return sock, reader
                reader.close()
                sock.close()
        return None

    def _open(self) -> _Connection:
        try:
            sock = socket.create_connection((self._host, self._port), timeout=self._timeout)
        except OSError as error:
            msg = f"memcached: can't connect to {self._host}:{self._port}: {error!r}"
            raise BackendError(msg) from error
        return sock, sock.makefile("rb")


def _read_answer(reader: IO[bytes]) -> Answer:
    answer, size = read_header(reader.readline())
    if size is None:
        return answer
    data = reader.read(size + 2)  # the value and its \r\n
    if len(data) < size + 2:
        msg = "memcached: the connection closed in the middle of a value"
        raise EOFError(msg)
    return Answer(code=answer.code, flags=answer.flags, value=data[:-2])


def _is_idle(sock: socket.socket, timeout: float) -> bool:
    """Whether sock is open with nothing to read: a closed one reads b"" at once, a desync reads bytes."""
    sock.settimeout(0)
    try:
        sock.recv(1, socket.MSG_PEEK)
    except BlockingIOError:
        return True
    except OSError:
        return False
    finally:
        sock.settimeout(timeout)
    return False

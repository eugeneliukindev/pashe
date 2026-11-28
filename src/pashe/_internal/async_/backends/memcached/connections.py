"""The connections of an async backend to memcached: written by hand for each side, as asyncio and sockets differ."""

from __future__ import annotations

import asyncio
import contextlib
from typing import TYPE_CHECKING, final

from pashe._internal.memcached.protocol import Answer, read_header
from pashe.errors import BackendError

if TYPE_CHECKING:
    from collections.abc import Sequence


@final
class AsyncMemcachedConnections:
    """Connections to one memcached, opened as calls need them and kept for the next ones.

    shortcut: no bound on how many are open, as many as calls run at once; add one if a service
    runs so many that memcached refuses connections.
    """

    __slots__ = ("_closed", "_host", "_idle", "_port", "_timeout")

    def __init__(
        self,
        host: str,
        port: int,
        timeout: float,
    ) -> None:
        self._host = host
        self._port = port
        self._timeout = timeout
        self._idle: list[tuple[asyncio.StreamReader, asyncio.StreamWriter]] = []
        self._closed = False

    async def send(self, commands: Sequence[bytes]) -> list[Answer]:
        """Send commands at once and read an answer for each, in their order, within the timeout.

        A memcached that can't be reached, takes longer or fails a command raises BackendError; the
        connection of a call that raised is closed, as an answer may be left unread on it.
        """
        reader, writer = self._reusable() or await self._open()
        try:
            async with asyncio.timeout(self._timeout):
                writer.write(b"".join(commands))
                await writer.drain()
                answers = [await _read_answer(reader) for _ in commands]  # noqa: WPS476 - one stream, read in order
        except BaseException as error:
            # a connection left in the middle of an answer would read it as the answer of the next call
            writer.close()
            if isinstance(error, OSError | EOFError):  # TimeoutError is an OSError
                msg = f"memcached: {error!r}"
                raise BackendError(msg) from error
            raise
        if self._closed:  # a call that ran on as the backend closed keeps nothing open
            await _close(writer)
        else:
            self._idle.append((reader, writer))
        return answers

    async def aclose(self) -> None:
        """Close every connection; one a call still holds closes as the call ends."""
        self._closed = True
        while self._idle:
            _, writer = self._idle.pop()
            await _close(writer)

    def _reusable(self) -> tuple[asyncio.StreamReader, asyncio.StreamWriter] | None:
        """An idle connection memcached still keeps open; one it closed, as on a restart, is dropped."""
        while self._idle:
            reader, writer = self._idle.pop()
            if not reader.at_eof() and not writer.is_closing():
                return reader, writer
            writer.close()
        return None

    async def _open(self) -> tuple[asyncio.StreamReader, asyncio.StreamWriter]:
        try:
            async with asyncio.timeout(self._timeout):
                return await asyncio.open_connection(self._host, self._port)
        except OSError as error:
            msg = f"memcached: can't connect to {self._host}:{self._port}: {error!r}"
            raise BackendError(msg) from error


async def _read_answer(reader: asyncio.StreamReader) -> Answer:
    answer, size = read_header(await reader.readline())
    if size is None:
        return answer
    data = await reader.readexactly(size + 2)  # the value and its \r\n
    return Answer(code=answer.code, flags=answer.flags, value=data[:-2])


async def _close(writer: asyncio.StreamWriter) -> None:
    writer.close()
    with contextlib.suppress(OSError):  # a connection that broke meanwhile is closed all the same
        await writer.wait_closed()

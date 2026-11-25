# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
# pyright: reportUnknownParameterType=false
# redis-py is typed in part: what its untyped methods return is unknown to pyright, as to mypy.
from __future__ import annotations

import asyncio
import contextlib
from typing import TYPE_CHECKING, final

from redis import asyncio as redis_asyncio
from redis.asyncio.cluster import RedisCluster as AsyncRedisCluster

from pashe._internal.redis.listening import INVALIDATE_CHANNEL, ReconnectBackoff, listening_connection, tracking_command
from pashe._internal.redis.messages import decode_message, read_invalidation

if TYPE_CHECKING:
    from redis.asyncio import Redis
    from redis.asyncio.client import PubSub
    from redis.asyncio.connection import AbstractConnection

    from pashe._internal.async_.backends.near import AsyncInvalidationHandler


@final
class AsyncPubSubListener:
    __slots__ = ("_channel", "_client", "_on_invalidate", "_retries", "_task")

    def __init__(
        self, client: Redis | AsyncRedisCluster, channel: str, on_invalidate: AsyncInvalidationHandler
    ) -> None:
        self._client = client
        self._channel = channel
        self._on_invalidate = on_invalidate

        self._retries = ReconnectBackoff()
        self._task = asyncio.create_task(self._listen())

    async def stop(self) -> None:
        self._task.cancel()
        await asyncio.wait({self._task})

    async def _listen(self) -> None:
        while True:
            try:
                if isinstance(self._client, AsyncRedisCluster):
                    # the same client back: a cluster not used yet knows no slots, so subscribe would fail
                    self._client = await self._client.initialize()
                async with self._client.pubsub(ignore_subscribe_messages=True) as pubsub:
                    await self._relay(pubsub)
            except redis_asyncio.RedisError:
                await self._on_invalidate(None)  # messages may have been lost meanwhile
                await asyncio.sleep(self._retries.next_delay())

    async def _relay(self, pubsub: PubSub) -> None:
        await pubsub.subscribe(self._channel)
        await self._on_invalidate(None)  # a copy made before the subscription may be old
        async for received in pubsub.listen():
            await self._on_invalidate(decode_message(received["data"]))  # its own too: a copy goes, read again


@final
class AsyncTrackingListener:
    __slots__ = ("_on_invalidate", "_pool", "_prefix", "_retries", "_task")

    def __init__(self, client: Redis, prefix: str, on_invalidate: AsyncInvalidationHandler) -> None:
        self._pool = client.connection_pool
        self._prefix = prefix
        self._on_invalidate = on_invalidate

        self._retries = ReconnectBackoff()
        self._task = asyncio.create_task(self._run())

    async def stop(self) -> None:
        self._task.cancel()
        await asyncio.wait({self._task})

    async def _run(self) -> None:
        while True:
            try:
                await self._listen()
            except redis_asyncio.RedisError:
                await self._on_invalidate(None)  # messages may have been lost meanwhile
                await asyncio.sleep(self._retries.next_delay())

    async def _listen(self) -> None:
        connection = listening_connection(self._pool.connection_class, self._pool.connection_kwargs)
        async with contextlib.AsyncExitStack() as held:
            held.push_async_callback(connection.disconnect)
            await connection.connect()  # type: ignore[no-untyped-call]  # redis-py leaves it untyped
            client_id = await self._command(connection, "CLIENT", "ID")
            await self._command(connection, *tracking_command(client_id, self._prefix))
            await self._command(connection, "SUBSCRIBE", INVALIDATE_CHANNEL)
            await self._on_invalidate(None)  # a copy made before tracking started may be old
            while True:
                received = await connection.read_response()
                tracked, keys = read_invalidation(received)
                if tracked:
                    await self._on_invalidate(keys)

    async def _command(self, connection: AbstractConnection, *command: str | int) -> object:
        await connection.send_command(*command)
        return await connection.read_response()

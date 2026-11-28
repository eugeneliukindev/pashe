# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
# pyright: reportUnknownParameterType=false
# redis-py is typed in part: what its untyped methods return is unknown to pyright, as to mypy.
from __future__ import annotations

import contextlib
import threading
from typing import TYPE_CHECKING, final

from redis import RedisError

from pashe._internal.redis.clients import translated_errors
from pashe._internal.redis.listening import (
    INVALIDATE_CHANNEL,
    POLL,
    ReconnectBackoff,
    listen_failure,
    listening_connection,
    tracking_command,
)
from pashe._internal.redis.messages import decode_message, read_invalidation

if TYPE_CHECKING:
    from redis import Redis
    from redis.client import PubSub, PubSubWorkerThread
    from redis.cluster import RedisCluster
    from redis.connection import AbstractConnection

    from pashe._internal.sync.backends.near import InvalidationHandler
    from pashe.hooks import Hook


@final
class PubSubListener:
    __slots__ = ("_hooks", "_on_invalidate", "_pubsub", "_retries", "_stopped", "_thread")

    def __init__(
        self,
        client: Redis | RedisCluster,
        channel: str,
        on_invalidate: InvalidationHandler,
        *,
        hooks: Hook,
    ) -> None:
        self._on_invalidate = on_invalidate
        self._hooks = hooks

        self._retries = ReconnectBackoff()
        self._stopped = threading.Event()  # wakes the wait before a retry, so stop returns at once
        self._pubsub = client.pubsub(ignore_subscribe_messages=True)  # type: ignore[no-untyped-call]  # redis-py leaves it untyped
        with translated_errors():  # a Redis that is down fails the read as BackendError, which the cache handles
            self._pubsub.subscribe(**{channel: self._message})
        self._thread = self._pubsub.run_in_thread(sleep_time=POLL, daemon=True, exception_handler=self._handle_lost)

    def stop(self) -> None:
        self._stopped.set()
        self._thread.stop()
        self._thread.join()
        self._pubsub.close()

    def _message(self, received: dict[str, object]) -> None:
        self._on_invalidate(decode_message(received["data"]))  # its own too: a copy goes, read again

    def _handle_lost(
        self,
        error: BaseException,
        _pubsub: PubSub,
        _thread: PubSubWorkerThread,
    ) -> None:
        # redis-py hands over every error of its thread, a bug of pashe or of a hook too
        if not isinstance(error, Exception):
            raise error  # such as SystemExit: the thread ends
        if isinstance(error, RedisError):
            self._on_invalidate(None)  # messages may have been lost meanwhile
        else:  # the error may be of on_invalidate itself: told, and the next message is read
            self._hooks.on_error(listen_failure(error))
        self._stopped.wait(self._retries.next_delay())


@final
class TrackingListener:
    __slots__ = ("_connection", "_hooks", "_on_invalidate", "_pool", "_prefix", "_retries", "_stopped", "_thread")

    def __init__(
        self,
        client: Redis,
        prefix: str,
        on_invalidate: InvalidationHandler,
        *,
        hooks: Hook,
    ) -> None:
        self._pool = client.connection_pool
        self._prefix = prefix
        self._on_invalidate = on_invalidate
        self._hooks = hooks

        self._retries = ReconnectBackoff()
        self._stopped = threading.Event()
        self._connection: AbstractConnection | None = None
        self._thread = threading.Thread(target=self._run, name="pashe-tracking", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stopped.set()
        connection = self._connection
        if connection is not None:
            connection.disconnect()  # type: ignore[no-untyped-call]  # redis-py leaves it untyped; wakes the read
        self._thread.join()

    def _run(self) -> None:
        while not self._stopped.is_set():
            try:
                self._listen()
            except RedisError:
                self._handle_lost()
            except Exception as error:  # noqa: BLE001 - told through on_error below
                if self._stopped.is_set() and isinstance(error, OSError | ValueError):
                    return  # a read of the socket stop closed fails so, past the errors of redis-py
                self._hooks.on_error(listen_failure(error))  # the next tracking drops every copy
                self._stopped.wait(self._retries.next_delay())

    def _handle_lost(self) -> None:
        if self._stopped.is_set():
            return
        self._on_invalidate(None)  # messages may have been lost meanwhile
        self._stopped.wait(self._retries.next_delay())

    def _listen(self) -> None:
        connection = listening_connection(self._pool.connection_class, self._pool.connection_kwargs)
        self._connection = connection
        with contextlib.ExitStack() as held:
            held.callback(connection.disconnect)
            connection.connect()
            client_id = self._command(connection, "CLIENT", "ID")
            self._command(connection, *tracking_command(client_id, self._prefix))
            self._command(connection, "SUBSCRIBE", INVALIDATE_CHANNEL)
            self._on_invalidate(None)  # a copy made before tracking started may be old
            while not self._stopped.is_set():
                received = connection.read_response()
                tracked, keys = read_invalidation(received)
                if tracked:
                    self._on_invalidate(keys)

    def _command(self, connection: AbstractConnection, *command: str | int) -> object:
        connection.send_command(*command)  # type: ignore[no-untyped-call]  # redis-py leaves it untyped
        return connection.read_response()

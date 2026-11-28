# ruff: noqa: RET504 - the page shows the backend it makes, as for the other backends
# --8<-- [start:imports]
from redis.asyncio.cluster import RedisCluster

from pashe.contrib.redis import AsyncRedisBackend

# --8<-- [end:imports]


async def main() -> AsyncRedisBackend:  # a cluster client meets its nodes when it is made
    # --8<-- [start:calls]
    backend = AsyncRedisBackend(RedisCluster.from_url("redis://node-1:7000"))
    # --8<-- [end:calls]
    return backend

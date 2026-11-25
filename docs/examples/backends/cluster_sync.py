# ruff: noqa: RET504 - the page shows the backend it makes, as for the other backends
# --8<-- [start:imports]
from redis.cluster import RedisCluster

from pashe.contrib.redis import RedisBackend

# --8<-- [end:imports]


def main() -> RedisBackend:  # a cluster client meets its nodes when it is made
    # --8<-- [start:calls]
    backend = RedisBackend(RedisCluster.from_url("redis://node-1:7000", socket_timeout=1))
    # --8<-- [end:calls]
    return backend

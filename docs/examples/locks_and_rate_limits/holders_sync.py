# --8<-- [start:show]
from pashe import Cache
from pashe.backends import MemoryBackend

cache = Cache(MemoryBackend())


@cache.locked(ttl=60, holders=3)  # at most three exports at once, in every process
def export(tenant: str) -> None: ...  # the work of yours that a few may do together


def main() -> None:
    with cache.lock("reports", ttl=60, holders=3):  # the same for a block
        export("acme")


# --8<-- [end:show]

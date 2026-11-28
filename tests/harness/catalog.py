"""The servers of servers.toml, read once into types of their own: pytest takes them, and so does nox.

It imports nothing of pytest, so noxfile.py can import it.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Literal, get_args

type ClusterProgram = Literal["redis", "valkey"]


@dataclass(frozen=True, slots=True, kw_only=True)
class RedisServer:
    image: str
    cluster_image: str
    cluster_program: ClusterProgram

    def __post_init__(self) -> None:
        if self.cluster_program not in get_args(ClusterProgram.__value__):
            msg = f"servers.toml: the cluster_program of {self.image} is {self.cluster_program!r}, not redis or valkey"
            raise ValueError(msg)


@dataclass(frozen=True, slots=True, kw_only=True)
class MemcachedServer:
    image: str


@dataclass(frozen=True, slots=True, kw_only=True)
class Family[S]:
    """The servers of one family, and which of them a run and nox -s lowest take."""

    default: str
    lowest: str
    servers: dict[str, S]

    def __post_init__(self) -> None:
        for role, name in (("default", self.default), ("lowest", self.lowest)):
            if name not in self.servers:
                msg = f"servers.toml: {role} is {name!r}, which names no server of its family"
                raise ValueError(msg)

    @property
    def others(self) -> list[str]:
        """The servers but the default, which runs in every other job of CI."""
        return [name for name in self.servers if name != self.default]


_CATALOG: Final = tomllib.loads(Path(__file__).with_name("servers.toml").read_text())

REDIS: Final = Family(
    default=_CATALOG["redis"]["default"],
    lowest=_CATALOG["redis"]["lowest"],
    servers={name: RedisServer(**server) for name, server in _CATALOG["redis"]["servers"].items()},
)
MEMCACHED: Final = Family(
    default=_CATALOG["memcached"]["default"],
    lowest=_CATALOG["memcached"]["lowest"],
    servers={name: MemcachedServer(**server) for name, server in _CATALOG["memcached"]["servers"].items()},
)

"""The tests that vary one axis of the matrix, beside the run of every Python with uv.lock and Redis 8 in CI.

Each axis varies on one Python, the others at their base: the lowest versions the dependencies allow
with the oldest server, the highest versions, every other server, and Python without the GIL. None
touches .venv or uv.lock: nox makes each environment under .nox and installs into it. Run ``nox -s lowest``,
``nox -s highest``, ``nox -s "servers(valkey-9)"`` or ``nox -s free_threaded-3.14t``, or a session alone
for all of its runs; arguments after ``--`` go to pytest. CI runs every session, each as a job.
"""

import sys
from pathlib import Path
from typing import Final, Literal

import nox

# nox puts the project on no path, and the catalog of the servers lives in the harness of the tests
sys.path.insert(0, str(Path(__file__).parent))
from tests.harness.catalog import MEMCACHED, REDIS

nox.needs_version = "==2026.10.20"  # the version pyproject.toml pins: another one is refused at once
nox.options.default_venv_backend = "uv"
nox.options.sessions = []  # each runs when named: every one takes Docker for Redis
nox.options.error_on_missing_interpreters = True
nox.options.error_on_external_run = True

type Resolution = Literal["lowest-direct", "highest"]  # the strategies of uv: the floors of the direct ones, the newest

_PYPROJECT: Final = nox.project.load_toml("pyproject.toml")
_PYTHONS: Final = nox.project.python_versions(_PYPROJECT)  # the classifiers: every Python pashe supports
_TESTS: Final = ("tests", "docs/examples")
_PROCESSES: Final = "4"  # as processes in the justfile


def _test(
    session: nox.Session,
    resolution: Resolution,
    *options: str,
) -> None:
    # the extras and the tests, resolved afresh from pyproject.toml; the lock is not read
    session.log(f"Python {session.python}, the versions of --resolution={resolution}")
    session.install(f"--resolution={resolution}", "-e", ".[all]", "--group", "test")
    session.run("uv", "pip", "list", external=True)  # what the run took, for the log
    session.run("pytest", "-n", _PROCESSES, *options, *(session.posargs or _TESTS))


# an old redis-py meets an old server at a user who upgrades neither: the floors run on the oldest of both
@nox.session(python=_PYTHONS[0])
def lowest(session: nox.Session) -> None:
    """Run the tests with the lowest versions the floors of the dependencies allow, over the oldest servers."""
    _test(session, "lowest-direct", "--redis-server", REDIS.lowest, "--memcached-server", MEMCACHED.lowest)


@nox.session(python=_PYTHONS[-1])
def highest(session: nox.Session) -> None:
    """Run the tests with the newest versions the upper bounds allow, past the lock."""
    _test(session, "highest")


@nox.session(python=_PYTHONS[-1])
@nox.parametrize("server", REDIS.others, ids=REDIS.others)
def servers(session: nox.Session, server: str) -> None:
    """Run the tests over a Redis, Valkey or Dragonfly server and its cluster, with the locked versions."""
    _sync(session)
    session.run("pytest", "-n", _PROCESSES, "--redis-server", server, *(session.posargs or _TESTS))


# experimental: the builds without the GIL are new, and CI reports their failures without blocking
@nox.session(python=["3.14t", "3.15t"], tags=["experimental"])
def free_threaded(session: nox.Session) -> None:
    """Run the tests on a Python without the GIL, with the locked versions."""
    _sync(session, "--no-install-package", "orjson")  # orjson has no build for a Python without the GIL
    session.run("pytest", "-n", _PROCESSES, *(session.posargs or _TESTS), env={"PYTHON_GIL": "0"})


def _sync(session: nox.Session, *args: str) -> None:
    # the versions of uv.lock, into the environment of the session instead of .venv
    session.run_install(
        "uv",
        "sync",
        "--locked",
        "--all-extras",
        "--group",
        "test",
        *args,
        env={"UV_PROJECT_ENVIRONMENT": session.virtualenv.location},
        external=True,
    )

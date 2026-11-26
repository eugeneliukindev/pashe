"""The tests over the lowest and the highest versions the dependencies allow, every server, and Python without the GIL.

None touches .venv or uv.lock: nox makes each environment under .nox and installs into it. Run
``nox -s lowest-3.12``, ``nox -s highest-3.15``, ``nox -s "servers(valkey-9)"`` or ``nox -s free_threaded-3.14t``, or a session
alone for all of its runs; arguments after ``--`` go to pytest. CI runs every session, each as a job.
"""

from typing import Final, Literal

import nox

nox.needs_version = "==2026.10.20"  # the version pyproject.toml pins: another one is refused at once
nox.options.default_venv_backend = "uv"
nox.options.sessions = []  # each runs when named: every one takes Docker for Redis
nox.options.error_on_missing_interpreters = True  # a Python it cannot find fails, instead of being skipped
nox.options.error_on_external_run = True  # a program outside the environment runs only when a session says so

type Resolution = Literal["lowest-direct", "highest"]  # the strategies of uv: the floors of the direct ones, the newest

_PYPROJECT: Final = nox.project.load_toml("pyproject.toml")
_PYTHONS: Final = nox.project.python_versions(_PYPROJECT)  # the classifiers: every Python pashe supports
_TESTS: Final = ("tests", "docs/examples")

# The server and the cluster of each run of servers: the oldest Redis with CLIENT TRACKING, still
# offered by clouds, to the newest Redis and Valkey. Dragonfly runs with no cluster of its own.
_SERVERS: Final = {
    "redis-6.2": ("redis:6.2-alpine", "redis:6.2-alpine"),
    "redis-7.4": ("redis:7.4-alpine", "redis:7.4-alpine"),
    "redis-8": ("redis:8-alpine", "redis:8-alpine"),
    "valkey-8": ("valkey/valkey:8-alpine", "valkey/valkey:8-alpine"),
    "valkey-9": ("valkey/valkey:9-alpine", "valkey/valkey:9-alpine"),
    "dragonfly": ("docker.dragonflydb.io/dragonflydb/dragonfly:latest", "redis:8-alpine"),
}


def _test(session: nox.Session, resolution: Resolution) -> None:
    # the extras and the tests, resolved afresh from pyproject.toml; the lock is not read
    session.log(f"Python {session.python}, the versions of --resolution={resolution}")
    session.install(f"--resolution={resolution}", "-e", ".[all]", "--group", "test")
    session.run("uv", "pip", "list", external=True)  # what the run took, for the log
    session.run("pytest", "-n", "auto", *(session.posargs or _TESTS))


@nox.session(python=_PYTHONS)
def lowest(session: nox.Session) -> None:
    """Run the tests with the lowest versions the floors of the dependencies allow."""
    _test(session, "lowest-direct")


@nox.session(python=_PYTHONS)
def highest(session: nox.Session) -> None:
    """Run the tests with the newest versions the upper bounds allow, past the lock."""
    _test(session, "highest")


@nox.session(python=_PYTHONS[-1])
@nox.parametrize(("image", "cluster_image"), list(_SERVERS.values()), ids=list(_SERVERS))
def servers(session: nox.Session, image: str, cluster_image: str) -> None:
    """Run the tests over a Redis, Valkey or Dragonfly server and its cluster, with the locked versions."""
    _sync(session)
    env = {"PASHE_TEST_REDIS_IMAGE": image, "PASHE_TEST_REDIS_CLUSTER_IMAGE": cluster_image}
    session.run("pytest", "-n", "auto", *(session.posargs or _TESTS), env=env)


# experimental: the builds without the GIL are new, and CI reports their failures without blocking
@nox.session(python=["3.14t", "3.15t"], tags=["experimental"])
def free_threaded(session: nox.Session) -> None:
    """Run the tests on a Python without the GIL, with the locked versions."""
    _sync(session, "--no-install-package", "orjson")  # orjson has no build for a Python without the GIL
    session.run("pytest", "-n", "auto", *(session.posargs or _TESTS), env={"PYTHON_GIL": "0"})


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

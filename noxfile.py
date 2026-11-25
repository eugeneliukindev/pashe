"""The tests over the lowest and the highest versions the dependencies allow, each in an environment of its own.

Neither touches .venv or uv.lock: nox makes each environment under .nox and installs into it. Run
``nox -s lowest-3.12`` or ``nox -s highest-3.15``, or a session alone for every Python; arguments
after ``--`` go to pytest.
"""

from typing import Final, Literal

import nox

nox.needs_version = "==2026.10.20"  # the version pyproject.toml pins: another one is refused at once
nox.options.default_venv_backend = "uv"
nox.options.sessions = []  # each runs when named: both take Docker for Redis
nox.options.error_on_missing_interpreters = True  # a Python it cannot find fails, instead of being skipped
nox.options.error_on_external_run = True  # a program outside the environment runs only when a session says so

type Resolution = Literal["lowest-direct", "highest"]  # the strategies of uv: the floors of the direct ones, the newest

_PYPROJECT: Final = nox.project.load_toml("pyproject.toml")
_PYTHONS: Final = nox.project.python_versions(_PYPROJECT)  # the classifiers: every Python pashe supports
_TESTS: Final = ("tests", "docs/examples")


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

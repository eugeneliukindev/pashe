set shell := ["bash", "-eu", "-o", "pipefail", "-c"]
set dotenv-load := false

# Do not update the environment when running
export UV_NO_SYNC := '1'

# lychee is a binary, not a Python package: it runs from its image
lychee_image := 'lycheeverse/lychee:latest'

# the tests of races and timing, by the words their names use: what test-flaky runs again and again
races := 'flight or cancel or invalidat or lock or slow or background or thread or revalidate or during_a_copy or probe or concurrent or waiter or processes or timeout'

[default]
[private]
help:
    @just --list --unsorted

[doc('Install every dependency group and extra')]
[group('dev')]
install *args='':
    uv sync --all-groups --all-extras {{ args }}

[doc('Regenerate the sync side, then format the code')]
[group('dev')]
fmt:
    # unasyncd exits 1 when it rewrote a file: that is what we asked for here.
    -uv run unasyncd --quiet
    uv run ruff format
    uv run ruff check --fix
    uv run tombi format

[doc('Run all linters')]
[group('dev')]
lint:
    uv run ruff check --exit-non-zero-on-fix
    uv run ruff format --check --diff
    uv run flake8 src src/pashe/_internal/sync/threads.py src/pashe/_internal/sync/locks/lock.py src/pashe/_internal/sync/backends/redis/listeners.py
    uv run pydoclint --quiet src
    uv run slotscheck -m pashe
    uv run lint-imports
    uv run deptry src
    uv run typos
    uv run codespell
    uv run tombi format --check
    uv run tombi lint
    just --fmt --check --unstable
    uv run actionlint
    uv run zizmor --no-progress .github/workflows
    uv run check-jsonschema --builtin-schema vendor.github-workflows .github/workflows/*.yml
    uv run pytest --dead-fixtures -n 0 --no-cov -p no:randomly --quiet

[doc('Run the type checkers')]
[group('dev')]
types:
    uv run mypy src tests docs/examples noxfile.py
    uv run pyright
    uv run pyrefly check

[doc('Run the linters, the type checkers and the dependency checks at once')]
[group('dev')]
[parallel]
check: lint types deps

[doc('Run everything CI runs: the checks, the tests and the examples of the docstrings and the docs')]
[group('dev')]
all *args='': check (test args) doctest docs-check

[doc('Run the tests, reports in coverage/: html/index.html, coverage.xml and junit.xml; Redis starts in Docker')]
[group('testing')]
[no-exit-message]
test *args='':
    uv run pytest -n auto --cov --cov-report=term --cov-report=xml --cov-report=html \
        --junitxml=coverage/junit.xml {{ args }}
    # strict-no-cover reads the data with a config of its own, which does not know data_file
    COVERAGE_FILE=coverage/.coverage uv run strict-no-cover

[doc('Run the tests over memory alone: no Docker, no coverage, one process')]
[group('testing')]
[no-exit-message]
test-fast *args='':
    uv run pytest -n 0 --no-cov -m 'not redis' {{ args }}

[doc('Run the examples of the docstrings; the async side is generated into the sync one and checked there')]
[group('testing')]
[no-exit-message]
doctest:
    uv run pytest -n 0 --no-cov -p no:randomly --doctest-modules src/pashe --ignore=src/pashe/_internal/async_
    # the modules of the async side written by hand have no generated twin to check them in
    uv run pytest -n 0 --no-cov -p no:randomly --doctest-modules src/pashe/_internal/async_/locks/lock.py src/pashe/_internal/async_/tasks.py

[doc('Run the tests of races and timing many times each over xdist, to catch one that passes by luck; after a change to them')]
[group('testing')]
test-flaky runs='100' *args='':
    uv run pytest -n auto --no-cov -p no:randomly --flake-finder --flake-runs={{ runs }} -k '{{ races }}' {{ args }}

[doc('Run the tests with the lowest versions the dependencies allow, on one Python or every one, in .nox: .venv and uv.lock stay')]
[group('testing')]
test-lowest python='' *args='':
    uv run nox -s lowest{{ if python == '' { '' } else { '-' + python } }} -- {{ args }}

[doc('Run the tests with the newest versions the bounds allow, past the lock, on one Python or every one, in .nox')]
[group('testing')]
test-highest python='' *args='':
    uv run nox -s highest{{ if python == '' { '' } else { '-' + python } }} -- {{ args }}

[doc('Run the tests over every server and its cluster, or one, such as valkey-9, with the locked versions, in .nox')]
[group('testing')]
test-servers server='' *args='':
    uv run nox -s servers{{ if server == '' { '' } else { '(' + server + ')' } }} -- {{ args }}

[doc('Run the tests on Python without the GIL, 3.14t or 3.15t or both, with the locked versions, in .nox')]
[group('testing')]
test-free-threaded python='' *args='':
    uv run nox -s free_threaded{{ if python == '' { '' } else { '-' + python } }} -- {{ args }}

[doc('Validate the lock file and the installed dependencies, and look for known vulnerabilities in them')]
[group('testing')]
deps:
    uv lock --check
    uv pip check
    uv audit --locked --preview-features audit-command  # the OSV database: every group and extra the lock holds

[doc('Build the documentation into site/; a warning fails the build')]
[group('docs')]
docs:
    uv run zensical build --clean --strict

[doc('Test the examples of the docs: each imports, and what a page says of it holds')]
[group('docs')]
docs-check:
    uv run pytest -n 0 --no-cov docs/examples

[doc('Serve the documentation with live reload')]
[group('docs')]
docs-serve:
    uv run zensical serve

[doc('Check every link of the docs and the docstrings')]
[group('docs')]
docs-links: (_lychee 'docs' 'src')

[private]
_lychee +paths:
    docker run --rm --volume "$PWD:/input:ro" --workdir /input {{ lychee_image }} --no-progress --extensions md,py {{ paths }}

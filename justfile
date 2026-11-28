set shell := ["bash", "-eu", "-o", "pipefail", "-c"]
set dotenv-load := false

export UV_NO_SYNC := '1'

# each starts a Redis and a cluster in Docker: more of them wait on Docker instead of running tests
processes := '4'

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
    -just unasyncd
    uv run ruff format
    uv run ruff check --fix
    uv run tombi format

[doc('Run every linter, one recipe each')]
[group('lint')]
lint: ruff flake8 pydoclint slotscheck import-linter deptry typos codespell rumdl vale tombi justfile actionlint zizmor workflows dead-fixtures

[doc('Generate the sync side from the async one; exits 1 when it rewrote a file, so a stale side fails')]
[group('lint')]
unasyncd:
    uv run unasyncd --quiet

[doc('Lint and check the format of the code with ruff')]
[group('lint')]
ruff:
    uv run ruff check --exit-non-zero-on-fix
    uv run ruff format --check --diff

[doc('Run wemake-python-styleguide and the plugins of flake8 that ruff has no rules for')]
[group('lint')]
flake8:
    uv run flake8 src src/pashe/_internal/sync/threads.py src/pashe/_internal/sync/locks/lock.py src/pashe/_internal/sync/backends/redis/listeners.py src/pashe/_internal/sync/backends/memcached/connections.py

[doc('Check that the docstrings match the signatures')]
[group('lint')]
pydoclint:
    uv run pydoclint --quiet src

[doc('Check the __slots__ of every class')]
[group('lint')]
slotscheck:
    uv run slotscheck -m pashe

[doc('Check that the modules import one another in the allowed directions')]
[group('lint')]
import-linter:
    uv run lint-imports

[doc('Check that the dependencies are declared as they are imported')]
[group('lint')]
deptry:
    uv run deptry src

[doc('Find typos with typos')]
[group('lint')]
typos:
    uv run typos

[doc('Find misspelled words with codespell')]
[group('lint')]
codespell:
    uv run codespell

[doc('Lint the Markdown of the docs and the README with rumdl')]
[group('lint')]
rumdl:
    uv run rumdl check docs README.md

[doc('Check the prose of the docs and the README against the glossary with Vale')]
[group('lint')]
vale:
    uv run vale docs README.md

[doc('Check the format of the TOML files, and lint them')]
[group('lint')]
tombi:
    uv run tombi format --check
    uv run tombi lint

[doc('Check the format of this justfile')]
[group('lint')]
justfile:
    just --fmt --check --unstable

[doc('Lint the GitHub workflows with actionlint')]
[group('lint')]
actionlint:
    uv run actionlint

[doc('Audit the GitHub workflows for security with zizmor')]
[group('lint')]
zizmor:
    uv run zizmor --no-progress .github/workflows

[doc('Validate the GitHub workflows against their schema')]
[group('lint')]
workflows:
    uv run check-jsonschema --builtin-schema vendor.github-workflows .github/workflows/*.yml

[doc('Find fixtures of the tests that no test uses')]
[group('lint')]
dead-fixtures:
    uv run pytest --dead-fixtures -n 0 --no-cov -p no:randomly --quiet

[doc('Run every type checker, one recipe each')]
[group('types')]
types: mypy pyright pyrefly

[doc('Check the types with mypy, strict')]
[group('types')]
mypy:
    uv run mypy src tests benchmarks docs/examples noxfile.py

[doc('Check the types with pyright')]
[group('types')]
pyright:
    uv run pyright

[doc('Check the types with pyrefly')]
[group('types')]
pyrefly:
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
    uv run pytest -n {{ processes }} --cov --cov-report=term --cov-report=xml --cov-report=html \
        --junitxml=coverage/junit.xml {{ args }}
    # strict-no-cover reads the data with a config of its own, which does not know data_file
    COVERAGE_FILE=coverage/.coverage uv run strict-no-cover

[doc('Run the tests over memory alone: no Docker, no coverage, one process')]
[group('testing')]
[no-exit-message]
test-fast *args='':
    uv run pytest -n 0 --no-cov -m 'not redis and not memcached' {{ args }}

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
    uv run pytest -n {{ processes }} --no-cov -p no:randomly --flake-finder --flake-runs={{ runs }} -k '{{ races }}' {{ args }}

[doc('Measure the codecs, the compressors and a call of a cache over each backend; Redis starts in Docker')]
[group('testing')]
bench *args='':
    # one process and no coverage, which would be measured too; every other run takes each benchmark once, as a test
    uv run pytest -n 0 --no-cov -p no:randomly --benchmark-enable --benchmark-columns=median,iqr,rounds \
        --benchmark-sort=name benchmarks {{ args }}

[doc('Run the tests with the lowest versions the dependencies allow, on Python 3.12 over the oldest servers of tests/harness/servers.toml, in .nox: .venv and uv.lock stay')]
[group('testing')]
test-lowest *args='':
    uv run nox -s lowest -- {{ args }}

[doc('Run the tests with the newest versions the bounds allow, past the lock, on Python 3.15, in .nox')]
[group('testing')]
test-highest *args='':
    uv run nox -s highest -- {{ args }}

[doc('Run the tests over every server and its cluster, or one, such as valkey-9, with the locked versions, in .nox')]
[group('testing')]
test-servers server='' *args='':
    # quoted: bash reads the parentheses of servers(valkey-9) as a subshell
    uv run nox -s 'servers{{ if server == '' { '' } else { '(' + server + ')' } }}' -- {{ args }}

[doc('Run the tests on Python without the GIL, 3.14t or 3.15t or both, with the locked versions, in .nox')]
[group('testing')]
test-free-threaded python='' *args='':
    uv run nox -s free_threaded{{ if python == '' { '' } else { '-' + python } }} -- {{ args }}

[doc('Run one session of noxfile.py, such as lowest or "servers(valkey-9)", as a job of CI does')]
[group('testing')]
nox session *args='':
    uv run nox -s '{{ session }}' -- {{ args }}

[doc('List the sessions of noxfile.py that CI runs, as JSON for the matrix of its jobs')]
[group('testing')]
nox-sessions:
    @uv run nox -l --json -s lowest highest servers free_threaded | jq -c 'map({session, python, tags})'

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
    # what a page shows and no test runs is a line missed; the run is at 95.85 and the bar may only go up
    COVERAGE_FILE=coverage/.coverage.examples uv run pytest -n 0 --cov=examples --cov-report=term-missing:skip-covered \
        --cov-fail-under=95 docs/examples

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

[doc('Fail unless the tag, such as v1.2.3, is v and the version of pyproject.toml')]
[group('release')]
[positional-arguments]
version-matches tag:
    #!/usr/bin/env bash
    set -euo pipefail
    version="$(uv version --short)"
    if [ "$1" != "v$version" ]; then  # the tag as an argument, never in the text of the script
        echo "::error::the tag is $1, pyproject.toml has version $version: publish v$version, or set the version first"
        exit 1
    fi

[doc('Build the sdist and the wheel into dist/, check what PyPI reads of them, and import the wheel alone')]
[group('release')]
build:
    uv build
    uvx twine check --strict dist/*
    uv run --isolated --no-project --with dist/*.whl python -c "import pashe; print(pashe.__version__)"

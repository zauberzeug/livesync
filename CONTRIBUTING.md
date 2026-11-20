# Contributing to LiveSync

Thank you for your interest in contributing to LiveSync!
Bug reports, feature requests and pull requests are welcome on [GitHub](https://github.com/zauberzeug/livesync).
For non-trivial changes, please open an issue first to discuss the approach.

Security vulnerabilities should not be reported in public issues; see [SECURITY.md](SECURITY.md).

## Setup

We use [uv](https://docs.astral.sh/uv/) for development:

```bash
git clone git@github.com:zauberzeug/livesync.git
cd livesync
uv sync
uv run pre-commit install
```

This creates a virtual environment in `.venv` with LiveSync installed in editable mode and installs the git hooks.
The tests also need `rsync` and `git` on your `PATH`.
Now you can change the code and run the `livesync` command with the modified code via `uv run livesync ...` (or activate the environment with `source .venv/bin/activate`).

## Checks

[pre-commit](https://pre-commit.com/) keeps `uv.lock` in sync with `pyproject.toml`, formats the code (autopep8, mdformat) and runs the linters (Ruff, mypy, codespell, zizmor).
The tools are configured in `pyproject.toml` and `.pre-commit-config.yaml`.

There are two kinds of tests:

- **Unit tests** in `tests/test_*.py`, run with pytest.
  The mutex tests run against several login shells and skip the ones that are not installed (`dash`, `fish`, `tcsh`).
- **End-to-end tests** in `tests/test_*.sh`, which sync between two Docker containers.
  See [tests/README.md](tests/README.md) for details.

### Before submitting a pull request

Run these commands and make sure they pass:

```bash
uv run pre-commit run --all-files
uv run pytest
```

If you changed how LiveSync syncs, watches or locks the target, also run the end-to-end tests (requires Docker):

```bash
cd tests && ./run.sh
```

CI runs all of them on every pull request, pytest on the lowest and highest supported Python version.

## Code

- Prefer simple solutions.
- Check the codebase for similar functionality before adding something new, and reuse it instead of duplicating it.
- Remove obsolete code instead of working around it.
  When fixing a bug, exhaust existing patterns before introducing a new one; if you must, remove the old one.
- Explain important and non-obvious code with plain comments.
  Use `# NOTE:` only to draw special attention, e.g. to changes that must be mirrored elsewhere or to hidden coupling between files.
  Older code still prefixes every comment with `NOTE:`; adapt it when you touch it anyway, not in a separate sweep.
- Use assertions for internal invariants and descriptive exceptions (`ValueError`, `RuntimeError`, …) for invalid input.
- Do not add a dependency if the standard library or existing code already covers it.
- LiveSync is a library: do not use global mutable state.

## Tests

- Test observable behavior, not internals: no private attributes, no patched machinery, no fake objects mirroring the code under test.
  If you find yourself building scaffolding to observe an internal mechanism, stop and find the user-visible effect instead.
- Read a recent test in the same file before writing a new one, and copy its shape.
- Verify once that a regression test fails when the fix is reverted.
  A test that has only ever been seen green proves nothing.
- You may skip a test when it could only be written by mirroring the implementation; give the reason in the pull request.

## Documentation

- Use semantic line breaks in Markdown files in the repository: one sentence per line.
- Do not hard-wrap prose on GitHub (issues, pull requests, comments); GitHub renders every line break.

## Releases

Create and push a tag with the new version (e.g. `v0.2.1`).
The publish workflow builds the package, uploads it to PyPI and creates a GitHub release.
Edit the release afterwards to describe the changes.

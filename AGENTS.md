# AI Agent Guidelines for LiveSync

This file gives AI agents project-specific guidance.
For setup, coding standards and tests, see [CONTRIBUTING.md](CONTRIBUTING.md).

## Working in this repository

- LiveSync runs `rsync` and `ssh` with values from the user's configuration (paths, ports, `.syncignore` patterns, `--on-change` commands).
  Quote everything that ends up in a shell command, and add a test for the quoting when you touch it.
- The mutex in `livesync/mutex.py` is shared between independent sources that may run different LiveSync versions.
  Keep the format of `~/.livesync_mutex` backward compatible.
- `.syncignore` patterns are evaluated twice: by rsync (filter rules from `livesync/syncignore.py`) and by the file watcher (pathspec).
  A change to one side must keep both sides in agreement; `tests/test_syncignore.py` checks this.
- Never commit the generated SSH key pair in `tests/.ssh`.

## Before claiming a task complete

Run the checks and review your diff for unintended changes:

```bash
uv run pre-commit run --all-files
uv run pytest
```

If the change affects syncing, watching or the mutex, also run the end-to-end tests (requires Docker):

```bash
cd tests && ./run.sh
```

## Attribution

Mark text posted with substantial AI contribution (pull request descriptions, issue and review comments) with the [Colophon](https://github.com/zauberzeug/colophon) sigil, and commits with a `Co-authored-by` trailer.

# LiveSync

Repeatedly synchronize local workspace with a (slow) remote machine.
It is available as [PyPI package](https://pypi.org/project/livesync/) and hosted on [GitHub](https://github.com/zauberzeug/livesync).

[![PyPI version](https://badge.fury.io/py/livesync.svg)](https://pypi.org/project/livesync/)
[![PyPI - Downloads](https://img.shields.io/pypi/dm/livesync)](https://pypi.org/project/livesync/)
[![GitHub commit activity](https://img.shields.io/github/commit-activity/m/zauberzeug/livesync)](https://github.com/zauberzeug/livesync/graphs/commit-activity)
[![GitHub issues](https://img.shields.io/github/issues/zauberzeug/livesync)](https://github.com/zauberzeug/livesync/issues)
[![GitHub license](https://img.shields.io/github/license/zauberzeug/livesync)](https://github.com/zauberzeug/livesync/blob/main/LICENSE)

## Use Case

[VS Code Remote Development](https://code.visualstudio.com/docs/remote/remote-overview) and similar tools are great as long as your remote machine is powerful enough.
But if your target is a Raspberry Pi, Jetson Nano/Xavier/Orin, Beagle Board or similar, it feels like coding in jelly.
Especially if you run powerful extensions like Pylance, GitHub Copilot or Duet AI.
LiveSync solves this by watching your code for changes and just copying the modifications to the slow remote machine.
So you can develop on your own machine (and run tests there in the background) while all your changes appear also on the remote.
It works best if you have some kind of reload mechanism in place on the target ([NiceGUI](https://nicegui.io), [FastAPI](https://fastapi.tiangolo.com/) or [Flask](https://flask.palletsprojects.com/) for example).

## Usage

### BASH

```bash
livesync <source> <username>@<host>
```

LiveSync uses rsync (SSH) to copy the files, so the `<username>@<host>` must be accessible via SSH (ideally by key, not password or passphrase, because it will be called over and over).

Press `CTRL-C` to abort the synchronization.

Positional arguments:

- `<source>`
  local folder
- `<target>`
  target user, host and path (e.g. user@host:~/path; path defaults to source folder name in home directory)
- `<rsync_args>`
  arbitrary rsync parameters after "--"

Options:

- `--ssh-port SSH_PORT`
  SSH port on target (default: 22)
- `--on-change ON_CHANGE`
  command to be executed on remote host after any file change (default: None)
- `--mutex-interval MUTEX_INTERVAL`
  interval in which mutex is updated (default: 10 seconds)
- `--ignore-mutex`
  ignore mutex (use with caution) (default: False)
- `--no-watch`
  don't keep watching the copied folders for changes after the sync (default: False)

### Python

Simple example (where `robot` is the ssh hostname of the target system):

```py
from livesync import Folder, sync

sync(
    Folder('.', 'robot:~/navigation'),
    Folder('../rosys', 'robot:~/rosys'),
)
```

The `sync` call will block until the script is aborted.
Only if `watch=False` is used, the `sync` call will end after copying the folders to the target once.
The `Folder` class allows to set the `port` and an `on_change` bash command which is executed after a sync has been performed.
Via the `rsync_args` build method you can pass additional options to configure rsync.

#### Version in the mutex

The mutex file (`~/.livesync_mutex`) on the target contains, per folder, a block with the source path, the current git revision in brackets and the `git status`.
If the source repository has git tags, LiveSync derives a [dunamai](https://github.com/mtkennerly/dunamai)-style version from them and writes it **into the brackets** instead of the bare commit hash, so the remote side can tell which revision it currently holds:

```
/path/to/navigation --> robot:~/navigation
[0.1.0.post43.dev0+3f6ee0e]
## main
```

The format is always `[<base>.post<N>.dev0+<short-hash>]`:

- `<base>` is the latest tag (a leading `v` is stripped), `<N>` the number of commits since that tag, and `<short-hash>` the current commit — so the exact revision is always included, even sitting right on a tag (`[0.1.0.post0.dev0+3f6ee0e]`).
- Without any tag the base is `0.0.0` and the distance is the total number of commits, e.g. `[0.0.0.post12.dev0+63e867f]`.
- A repository without any commit yet, or a source that is not a git repository, gets no revision brackets at all.

The version is recomputed from git on every mutex update (roughly every `mutex_interval` seconds), so it stays live while syncing.
It is derived purely from `git` (no extra dependency): this is close to dunamai's PEP 440 output but not identical (dunamai drops the `.post0.dev0+<hash>` suffix on an exact tag, and does not replicate custom tag patterns, pre-releases, epochs or dirty markers).
The string contains no `"` characters, so it survives the `"`→`'` replacement LiveSync applies across the whole summary.

**Parser contract for the target side:** read the content of the `[...]` brackets on the revision line of each folder block; it is `<base>.post<N>.dev0+<short-hash>`.

Advanced example:

```py
import argparse
from livesync import Folder, sync

parser = argparse.ArgumentParser(description='Sync local code with robot.')
parser.add_argument('robot', help='Robot hostname')

args = parser.parse_args()

touch = 'touch ~/robot/main.py'
sync(
    Folder('.', f'{args.robot}:~/navigation', on_change='touch ~/navigation/main.py'),
    Folder('../rosys', f'{args.robot}:~/rosys').rsync_args(add='-L', remove='--checksum'),
    mutex_interval=30,
)
```

### Notes

- We suggest you have some auto-reloading in place on the (slow) target machine, like [NiceGUI](https://nicegui.io).
- Only one user per target host should run LiveSync at a time. Therefore LiveSync provides a mutex mechanism.
- You can create a `.syncignore` file in any source directory to skip additional files and directories from syncing.
- If a `.syncignore` file doesn't exist, it is automatically created containing `.git/`, `__pycache__/`, `.DS_Store`, `*.tmp`, and `.env`.

## Installation

```bash
python3 -m pip install livesync
```

## Development

For development we suggest to use the following instructions instead of the normal pip installation:

```bash
git clone git@github.com:zauberzeug/livesync.git
cd livesync
python3 -m pip uninstall livesync # remove previous installed version
python3 -m pip install -e .
```

Now you can change the code and call the `livesync` command from your `$PATH` variable with the modified code.

## Testing

We have build a small testing infrastructure with two docker containers.
See [tests/README.md](https://github.com/zauberzeug/livesync/blob/main/tests/README.md) for details.

## Releases

Just create and push a new tag with the new version name (v0.2.1 for example).
After a successful build a new release will be created.
This should be edited to describe the changes in the release notes.

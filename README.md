# LiveSync

Repeatedly synchronize local workspace with a (slow) remote machine.
Its available as [PyPI package](https://pypi.org/project/livesync/) and hosted on [GitHub](https://github.com/zauberzeug/livesync).

[![PyPI version](https://badge.fury.io/py/livesync.svg)](https://pypi.org/project/livesync/)
[![PyPI - Downloads](https://img.shields.io/pypi/dm/livesync)](https://pypi.org/project/livesync/)
[![GitHub commit activity](https://img.shields.io/github/commit-activity/m/zauberzeug/livesync)](https://github.com/zauberzeug/livesync/graphs/commit-activity)
[![GitHub issues](https://img.shields.io/github/issues/zauberzeug/livesync)](https://github.com/zauberzeug/livesync/issues)
[![GitHub forks](https://img.shields.io/github/forks/zauberzeug/livesync)](https://github.com/zauberzeug/livesync/network)
[![GitHub stars](https://img.shields.io/github/stars/zauberzeug/livesync)](https://github.com/zauberzeug/livesync/stargazers)
[![GitHub license](https://img.shields.io/github/license/zauberzeug/livesync)](https://github.com/zauberzeug/livesync/blob/main/LICENSE)

## Use Case

[VS Code Remote Development](https://code.visualstudio.com/docs/remote/remote-overview) and similar tools are great as long as your remote machine is powerful enough.
But if your target is a Raspberry Pi, Jetson Nano/Xavier/Orin, Beagle Board or similar, it feels like coding in yelly.
Especially if you run powerful extensions like Pylance.
LiveSync solves this by watching your code and just copying the changed files to the slow remote machine.
It works best if you have some kind of reloading mechanism in place on the target ([NiceGUI](https://nicegui.io) for example).

## Usage

```bash
cd <my_folder_with_vscode_workspace>
livesync <username>@<host>
```

LiveSync uses rsync (SSH) to copy the files, so the `<username>@<host>` must be accessible via SSH (ideally by key, not password or passphrase, because it will be called over and over).

Press `CTRL-C` to abort the synchronization.

### Notes

- We suggest you have some auto-reloading in place on the (slow) target machine, like [NiceGUI](https://nicegui.io).
- Only one user per target host should run LiveSync at a time. Therefore LiveSync provides a mutex mechanism.
- By default `.git/` folders are not synchronized.
- All files and directories from the `.gitignore` of any source directory are also excluded from synchronization.
- You can create a `.syncignore` file in any source directory to skip additional files and directories from syncing.
- If LiveSync finds a vscode-workspace file it will synchronize each directory listed in the `folders` section.

### Options

- `--on-change [command]` command to be executed on remote host after any file change
- `--source [SOURCE]` source folder on local host instead of vscode workspace file
- `--mutex-interval [INTERVAL]` interval in which mutex is updated

## Install

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

Now you can change the code and call the `livesync` command from your `$PATH` variable whith the modified code.

## Testing

We have build a small testing infrastructure with two docker containers.
See [tests/README.md](https://github.com/zauberzeug/livesync/blob/main/tests/README.md) for details.

## Releases

Just create and push a new tag with the new version name (v0.2.1 for example).
After successful build a new release will be created.
This should be edited to describe the changes.

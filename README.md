# LiveSync

Repeatedly synchronize local workspace with a (slow) remote machine.

## Use Case

[VS Code Remote Development](https://code.visualstudio.com/docs/remote/remote-overview) and similar tools are great as long as your remote machine is powerful enough.
But if your target is a Raspberry Pi, Jetson Nano/Xavier/Orin, Beagle Board or similar, it feels like coding in yelly.
Especially if you run powerful extensions like Pylance.
LiveSync solves this by watching your code and just copying the changed files to the slow remote machine.
It works best if you have some kind of reloading mechanism in place on the target.
We obviously recommend [NiceGUI](https://nicegui.io).

## Install

```bash
python3 -m pip install livesync
```

## Usage

```bash
cd <my_folder_with_vscode_workspace>
livesync <username>@<host>
```

LiveSync uses rsync (SSH) to copy the files, so the `<username>@<host>` must be accessible via SSH (ideally by key, not password or passphrase, because it will be called over and over).

Press `CTRL-C` to abort the synchronization.

### Notes

- We suggest you have some auto-reloading in place on the (slow) target machine, like [NiceGUI](https://nicegui.io).
- Only one user per target host can run LiveSync at a time.
- By default `.git/` folders are not synchronized.
- All files and directories from the `.gitignore` of any source directory are also excluded from synchronization.
- You can create a `.syncignore` file in any source directory to skip additional files and directories from syncing.

## Development

```bash
git clone git@github.com:zauberzeug/livesync.git
cd livesync
python3 -m pip uninstall livesync # remove previous installed version
python3 -m pip install -e .
```

Now you can change the code and still use the `livesync` command from your `$PATH` variable.

## Releases

Just create and push a new tag with the new version name.

#!/usr/bin/env python3
import argparse
import asyncio
import json
import sys
from glob import glob
from pathlib import Path
from typing import List

from livesync import Folder, Mutex


def git_summary(folders: List[Folder]) -> str:
    return '\n'.join(f.get_summary() for f in folders).replace('"', '\'')


async def async_main() -> None:
    parser = argparse.ArgumentParser(description='Repeatedly synchronize local workspace with remote machine')
    parser.add_argument('--on-change', type=str, help='command to be executed on remote host after any file change')
    parser.add_argument('--source', type=str, help='source folder on local host instead of VSCode workspace file')
    parser.add_argument('--mutex-interval', type=int, nargs='?', default=10,
                        help='interval in which mutex is updated')  # TODO why is nargs set?
    parser.add_argument('--target-root', type=str, default='', help='subbfolder on target to synchronize to')
    parser.add_argument('--target-port', type=int, default=22, help='ssh port on target')
    parser.add_argument('host', type=str, help='the target host (e.g. username@hostname)')
    args = parser.parse_args()

    folders: List[Folder] = []
    workspaces = glob('*.code-workspace')
    if args.source is None:
        if len(workspaces) == 0:
            print('No VSCode workspace file found.')
            print('Provide --source argument or run livesync in a directory with a *.code-workspace file.')
            sys.exit(1)
        if len(workspaces) > 1:
            print('Multiple VSCode workspace files found.')
            print('Provide --source argument or run livesync in a directory with a single *.code-workspace file.')
            sys.exit(1)

        print(f'Reading VSCode workspace file {workspaces[0]}...')
        with open(workspaces[0]) as f:
            workspace = json.load(f)
            folders = [f for f in [Folder(Path(folder['path']), args) for folder in workspace['folders']] if f.is_valid]

    else:
        folders = [Folder(Path(args.source), args)]

    print('Checking mutex...')
    mutex = Mutex(args.host)
    if not mutex.set(git_summary(folders)):
        print(f'Target is in use by {mutex.occupant}')
        sys.exit(1)

    print('Initial sync...')
    for folder in folders:
        print(f'  {folder.local_dir} --> {folder.ssh_target}')
        folder.sync(post_sync_command=args.on_change)

    print('Watching for file changes...')
    for folder in folders:
        asyncio.create_task(folder.watch(on_change_command=args.on_change))

    while mutex.set(git_summary(folders)):
        await asyncio.sleep(args.mutex_interval)


def main():
    try:
        asyncio.run(async_main())
    except KeyboardInterrupt:
        print('Bye!')


if __name__ == '__main__':
    main()

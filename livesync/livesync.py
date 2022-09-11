#!/usr/bin/env python3
import argparse
import asyncio
import json
import sys
from glob import glob
from typing import List

from livesync import Folder, Mutex


def git_summary(folders: List[Folder]) -> str:
    return '\n'.join(f.get_summary() for f in folders).replace('"', '\'')


async def async_main() -> None:
    parser = argparse.ArgumentParser(description='Repeatedly synchronize local workspace with remote machine')
    parser.add_argument('--on-change', type=str, help='command to be executed on remote host after any file change')
    parser.add_argument('--source', type=str, help='source folder on local host instead of vscode workspace file')
    parser.add_argument('--mutex-interval', type=int, nargs='?', default=10, help='interval in which mutex is updated')
    parser.add_argument('host', type=str, help='the target host (e.g. username@hostname)')
    args = parser.parse_args()

    folders: List[Folder] = []
    workspaces = glob('*.code-workspace')
    if args.source is None and workspaces:
        print(f'Reading vscode workspace file {workspaces[0]} ...')
        try:
            with open(workspaces[0]) as f:
                workspace = json.load(f)
                folders = [Folder(folder['path'], args.host) for folder in workspace['folders']]
        except IndexError:
            print('No vscode workspace file found; provide --source parameter or start in dir with *.code-workspace file')
            sys.exit(1)
    else:
        folders = [Folder(args.source or '.', args.host)]

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

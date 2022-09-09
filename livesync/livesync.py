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


async def main() -> None:
    parser = argparse.ArgumentParser(description='Repeatedly synchronize local workspace with remote machine')
    parser.add_argument('--on-change', type=str, help='command to be executed on remote host after any file change')
    parser.add_argument('host', type=str, help='the target host (e.g. username@hostname)')
    args = parser.parse_args()

    print('Reading workspace file...')
    with open(glob('*.code-workspace')[0]) as f:
        workspace = json.load(f)
        folders = [Folder(folder['path'], args.host) for folder in workspace['folders']]

    print('Checking mutex...')
    mutex = Mutex(args.host)
    if not mutex.set(git_summary(folders)):
        print(f'Target is in use by {mutex.occupant}')
        sys.exit(1)

    print('Initial sync...')
    for folder in folders:
        print(f'  {folder.local_dir} --> {folder.ssh_target}')
        folder.sync()

    print('Watching for file changes...')
    for folder in folders:
        asyncio.create_task(folder.watch(on_change_command=args.on_change))

    while mutex.set(git_summary(folders)):
        await asyncio.sleep(10)

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print('Bye!')

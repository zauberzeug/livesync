#!/usr/bin/env python3
import argparse
import asyncio
import sys
from pathlib import Path
from typing import List

import pyjson5

from livesync import Folder, Mutex, Target


def git_summary(folders: List[Folder]) -> str:
    return '\n'.join(f.get_summary() for f in folders).replace('"', '\'')


async def async_main() -> None:
    parser = argparse.ArgumentParser(
        description='Repeatedly synchronize local directories with remote machine',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('source', type=str, help='local source folder or VSCode workspace file')
    parser.add_argument('--target-path', type=str, default='', help='directory on target to synchronize to')
    parser.add_argument('--target-port', type=int, default=22, help='SSH port on target')
    parser.add_argument('--on-change', type=str, help='command to be executed on remote host after any file change')
    parser.add_argument('--mutex-interval', type=int, default=10, help='interval in which mutex is updated')
    parser.add_argument('host', type=str, help='the target host (e.g. username@hostname)')
    args = parser.parse_args()
    source = Path(args.source)

    folders: List[Folder] = []
    if source.is_file():
        workspace = pyjson5.decode(source.read_text())
        for path in [Path(f['path']) for f in workspace['folders']]:
            target_path = Path(args.target_path) / path.resolve().name
            folders.append(Folder(path, Target(host=args.host, port=args.target_port, path=target_path)))
    else:
        target_path = Path(args.target_path)
        if not args.target_path:
            target_path = Path(args.target_path) / source.resolve().name
        folders.append(Folder(source, Target(host=args.host, port=args.target_port, path=target_path)))

    for folder in folders:
        if not folder.local_path.is_dir():
            print(f'Invalid path: {folder.local_path}')
            sys.exit(1)

    print('Checking mutex...')
    mutex = Mutex(args.host, args.target_port)
    if not mutex.set(git_summary(folders)):
        print(f'Target is in use by {mutex.occupant}')
        sys.exit(1)

    if args.target_path:
        print('Creating target directory...')
        Target(host=args.host, port=args.target_port, path=Path(args.target_path)).make_target_directory()

    print('Initial sync...')
    for folder in folders:
        print(f'  {folder.local_path} --> {folder.ssh_path}')
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

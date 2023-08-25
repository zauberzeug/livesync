#!/usr/bin/env python3
import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import List

from livesync import Folder, Mutex, Target


def git_summary(folders: List[Folder]) -> str:
    return '\n'.join(f.get_summary() for f in folders).replace('"', '\'')


async def async_main() -> None:
    parser = argparse.ArgumentParser(description='Repeatedly synchronize local workspace with remote machine')
    parser.add_argument('--on-change', type=str, help='command to be executed on remote host after any file change')
    parser.add_argument('--source', type=str, help='source folder on local host instead of VSCode workspace file')
    parser.add_argument('--mutex-interval', type=int, default=10, help='interval in which mutex is updated')
    parser.add_argument('--target-root', type=str, default='', help='subfolder on target to synchronize to')
    parser.add_argument('--target-port', type=int, default=22, help='SSH port on target')
    parser.add_argument('host', type=str, help='the target host (e.g. username@hostname)')
    args = parser.parse_args()
    target = Target(host=args.host, port=args.target_port, root=Path(args.target_root))

    folders: List[Folder] = []
    workspaces = list(Path.cwd().glob('*.code-workspace'))
    if args.source is None and workspaces:

        if len(workspaces) > 1:
            print('Multiple VSCode workspace files found.')
            print('Provide --source argument or run livesync in a directory with a single *.code-workspace file.')
            sys.exit(1)

        print(f'Reading VSCode workspace file {workspaces[0]}...')

        workspace = json.loads(workspaces[0].read_text())
        paths = [Path(f['path']) for f in workspace['folders']]
        folders = [Folder(p, target) for p in paths if p.is_dir()]
    else:
        source_path = Path(args.source or '.')
        if not source_path.is_dir():
            print(f'Invalid source path: {source_path}')
            sys.exit(1)

        folders = [Folder(source_path, target)]

    print('Checking mutex...')
    mutex = Mutex(target)
    if not mutex.set(git_summary(folders)):
        print(f'Target is in use by {mutex.occupant}')
        sys.exit(1)

    if args.target_root:
        print('Creating target root directory...')
        target.make_target_root_directory()

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

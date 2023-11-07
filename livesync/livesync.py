#!/usr/bin/env python3
import argparse
import asyncio
import sys
from pathlib import Path

from livesync import Folder, Mutex


def git_summary(folder: Folder) -> str:
    return folder.get_summary().replace('"', '\'')


async def async_main() -> None:
    parser = argparse.ArgumentParser(
        description='Repeatedly synchronize a local directory with a remote machine',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('source', type=str, default='.', help='local source folder')
    parser.add_argument('target', type=str, help='target path (e.g. username@hostname:/path/to/target)')
    parser.add_argument('--ssh-port', type=int, default=22, help='SSH port on target')
    parser.add_argument('--on-change', type=str, help='command to be executed on remote host after any file change')
    parser.add_argument('--mutex-interval', type=int, default=10, help='interval in which mutex is updated')
    parser.add_argument('rsync_args', nargs=argparse.REMAINDER, help='arbitrary rsync parameters after "--"')
    args = parser.parse_args()
    source = Path(args.source)
    target = args.target
    if ':' not in target:
        target = f'{target}:{source.name}'
    rsync_args = ' '.join(args.rsync_args)

    folder = Folder(source, target, ssh_port=args.ssh_port, on_change=args.on_change).rsync_args(rsync_args)

    print('Checking mutex...')
    mutex = Mutex(args.host, args.target_port)
    if not mutex.set(git_summary(folder)):
        print(f'Target is in use by {mutex.occupant}')
        sys.exit(1)

    print('Initial sync...')
    print(f'  {folder.source_path} --> {folder.target}')

    print('Watching for file changes...')
    asyncio.create_task(folder.watch())

    while mutex.set(git_summary(folder)):
        await asyncio.sleep(folder.mutex_interval)


def main():
    try:
        asyncio.run(async_main())
    except KeyboardInterrupt:
        print('Bye!')


if __name__ == '__main__':
    main()

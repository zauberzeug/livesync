#!/usr/bin/env python3
import argparse

from livesync import Folder, sync


def main():
    parser = argparse.ArgumentParser(
        description='Repeatedly synchronize a local directory with a remote machine',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('source', type=str, default='.', help='local source folder')
    parser.add_argument('target', type=str, help='target path (e.g. username@hostname:/path/to/target)')
    parser.add_argument('--ssh-port', type=int, default=22, help='SSH port on target')
    parser.add_argument('--on-change', type=str, help='command to be executed on remote host after any file change')
    parser.add_argument('--mutex-interval', type=int, default=10, help='interval in which mutex is updated')
    parser.add_argument('--ignore-mutex', action='store_true', help='ignore mutex (use with caution)')
    parser.add_argument('rsync_args', nargs=argparse.REMAINDER, help='arbitrary rsync parameters after "--"')
    args = parser.parse_args()

    folder = Folder(args.source, args.target, ssh_port=args.ssh_port, on_change=args.on_change)
    folder.rsync_args(' '.join(args.rsync_args))
    sync(folder, mutex_interval=args.mutex_interval, ignore_mutex=args.ignore_mutex)


if __name__ == '__main__':
    main()

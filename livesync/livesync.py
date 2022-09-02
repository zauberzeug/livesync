#!/usr/bin/env python3
import argparse
import json
import os
import signal
import subprocess
import sys
import time
from datetime import datetime
from glob import glob
from typing import List

from livesync import Mutex
from livesync.folder import Folder

processes: List[subprocess.Popen] = []


def start_process(command: str) -> None:
    proc = subprocess.Popen(command, shell=True, preexec_fn=os.setsid, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    processes.append(proc)


def sync(folder: Folder) -> None:
    if not folder.is_valid:
        return
    print(f'start syncing "{folder.local_dir}" to "{folder.ssh_target}"')
    exclude_args = ' '.join([f'--exclude="{e}"' for e in folder.get_excludes()])
    rsync_args = '--prune-empty-dirs --delete -avz --itemize-changes'
    rsync = f'rsync {rsync_args} {exclude_args} {folder.local_dir}/ {folder.ssh_target}'
    start_process(rsync)
    start_process(f'fswatch -r -l 0.1 -o {folder.local_dir} {exclude_args} | xargs -n1 -I{{}} {rsync}')


def git_summary(folders: List[Folder]) -> str:
    summary = ''
    for folder in folders:
        summary += f'\n{folder.local_dir} --> {folder.ssh_target}\n'
        try:
            cmd = ['git', 'log', "--pretty=format:[%h]\n", '-n', '1']
            summary += subprocess.check_output(cmd, cwd=folder.local_dir).decode()
            cmd = ['git', 'status', '--short', '--branch']
            summary += subprocess.check_output(cmd, cwd=folder.local_dir).decode()
        except:
            pass  # maybe no git installed
    return summary.replace('"', '\'')


def main() -> None:
    parser = argparse.ArgumentParser(description='Repeatedly synchronize local workspace with remote machine')
    parser.add_argument('host', type=str, help='the target host (eg. username@hostname)')
    args = parser.parse_args()

    with open(glob('*.code-workspace')[0]) as f:
        workspace = json.load(f)
        folders = [Folder(folder['path'], args.host) for folder in workspace['folders']]
    mutex = Mutex(args.host)
    if not mutex.set(git_summary(folders)):
        print(f'Target is in use by {mutex.occupant}')
        sys.exit(1)
    try:
        for folder in folders:
            sync(folder)
        while mutex.set(git_summary(folders)):
            for _ in range(100):
                for p in processes:
                    # make stdout non-blocking (https://stackoverflow.com/a/59291466/364388)
                    os.set_blocking(p.stdout.fileno(), False)
                    line = str(p.stdout.readline().decode())
                    # only print files transferred to remote (see itemize-changes rsync option)
                    if line.startswith('<'):
                        print(f'{datetime.now().strftime("%X")} deploying: {line[10:].strip()}', flush=True)
                time.sleep(0.1)
        else:
            print(f'Target is in use by {mutex.occupant}')
    except KeyboardInterrupt:
        mutex.remove()
    finally:
        print('stopping sync')
        for p in processes:
            try:
                os.killpg(os.getpgid(p.pid), signal.SIGTERM)
            except:
                pass


if __name__ == '__main__':
    main()

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

from livesync import Mutex

processes: list[subprocess.Popen] = []


def start_process(command: str) -> None:
    proc = subprocess.Popen(command, shell=True, preexec_fn=os.setsid, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    processes.append(proc)


def parse_ignore_file(path: str) -> list[str]:
    if not os.path.isfile(path):
        return []
    with open(path) as f:
        return [line.strip() for line in f.readlines() if not line.startswith('#')]


def sync(path: str, target_host: str) -> None:
    if not os.path.isdir(path):
        return
    print(f'start syncing "{path}"')
    excludes = ['.git/', '__pycache__/', '.DS_Store'] \
        + parse_ignore_file(f'{path}/.syncignore') + parse_ignore_file(f'{path}/.gitignore')
    exclude_params = ' '.join([f'--exclude="{e}"' for e in excludes])
    rsync = f'rsync --prune-empty-dirs --delete -avz --itemize-changes {exclude_params} {path}/ {target_host}:{os.path.basename(os.path.realpath(path))}'
    start_process(rsync)
    start_process(f'fswatch -r -l 0.1 -o {path} {exclude_params} | xargs -n1 -I{{}} {rsync}')


def main():

    parser = argparse.ArgumentParser(description='Repeatedly synchronize local workspace with remote machine')
    parser.add_argument('host', type=str, help='the target host (eg. username@hostname)')
    args = parser.parse_args()

    mutex = Mutex(args.host)
    if not mutex.set():
        print(f'Target is in use by {mutex.occupant}')
        sys.exit(1)
    with open(glob('*.code-workspace')[0]) as f:
        workspace = json.load(f)
    try:
        for p in workspace['folders']:
            sync(p['path'], args.host)
        while mutex.set():
            for i in range(100):
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

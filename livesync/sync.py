import asyncio
import sys
from typing import Iterable

from .folder import Folder
from .mutex import Mutex


def get_summary(folders: Iterable[Folder]) -> str:
    return '\n'.join(folder.get_summary() for folder in folders).replace('"', '\'')


async def run_folder_tasks(folders: Iterable[Folder], mutex_interval: float, ignore_mutex: bool = False) -> None:
    try:
        if not ignore_mutex:
            summary = get_summary(folders)
            mutexes = {folder.host: Mutex(folder.host, folder.ssh_port) for folder in folders}
            for mutex in mutexes.values():
                print(f'Checking mutex on {mutex.host}', flush=True)
                if not mutex.set(summary):
                    print(f'Target is in use by {mutex.occupant}')
                    sys.exit(1)

        for folder in folders:
            print(f'  {folder.source_path} --> {folder.target}', flush=True)
            folder.sync()

        for folder in folders:
            print(f'Watch folder {folder.source_path}', flush=True)
            asyncio.create_task(folder.watch())

        while True:
            if not ignore_mutex:
                summary = get_summary(folders)
                for mutex in mutexes.values():
                    if not mutex.set(summary):
                        break
            await asyncio.sleep(mutex_interval)
    except Exception as e:
        print(e)


def sync(*folders: Folder, mutex_interval: float = 10, ignore_mutex: bool = False) -> None:
    try:
        asyncio.run(run_folder_tasks(folders, mutex_interval, ignore_mutex=ignore_mutex))
    except KeyboardInterrupt:
        print('Bye!')

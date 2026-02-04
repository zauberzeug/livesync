import asyncio
import sys
from typing import Iterable, List, Tuple

from .folder import Folder
from .mutex import Mutex


def get_summary(folders: Iterable[Folder]) -> str:
    return '\n'.join(folder.get_summary() for folder in folders).replace('"', '\'')


async def run_folder_tasks(
        folders: Iterable[Folder],
        mutex_interval: float, ignore_mutex: bool = False, watch: bool = True) -> None:
    try:
        if not ignore_mutex:
            summary = get_summary(folders)
            mutexes = {folder.host: Mutex(folder.host, folder.ssh_port) for folder in folders}
            for mutex in mutexes.values():
                print(f'Checking mutex on {mutex.host}', flush=True)
                if not await mutex.set(summary):
                    print(f'Target is in use by {mutex.occupant}')
                    sys.exit(1)

        for folder in folders:
            print(f'  {folder.source_path} --> {folder.target}', flush=True)
            await folder.sync()

        if watch:
            tasks: List[Tuple[Folder, asyncio.Task]] = []
            for folder in folders:
                print(f'Watch folder {folder.source_path}', flush=True)
                tasks.append((folder, asyncio.create_task(folder.watch())))

            while True:
                if not ignore_mutex:
                    summary = get_summary(folders)

                    for host in list(mutexes):
                        if await mutexes[host].set(summary):
                            continue
                        print(f'Target {host} is in use by {mutexes[host].occupant}, stopping watch tasks', flush=True)
                        [task.cancel() for folder, task in tasks if folder.host == host]
                        tasks = [(folder, task) for folder, task in tasks if folder.host != host]
                        del mutexes[host]

                    if not tasks:
                        print('No more folders to watch, exiting', flush=True)
                        break
                await asyncio.sleep(mutex_interval)
    except Exception as e:
        print(e)


def sync(*folders: Folder, mutex_interval: float = 10, ignore_mutex: bool = False, watch: bool = True) -> None:
    try:
        asyncio.run(run_folder_tasks(folders, mutex_interval, ignore_mutex=ignore_mutex, watch=watch))
    except KeyboardInterrupt:
        print('Bye!')

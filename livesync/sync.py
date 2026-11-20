import asyncio
import sys
from collections.abc import Iterable

from .folder import Folder
from .mutex import Mutex


def sync(*folders: Folder, mutex_interval: float = 10, ignore_mutex: bool = False, watch: bool = True) -> None:
    """Synchronize one or more folders, optionally watching for changes."""
    try:
        asyncio.run(_run_folder_tasks(folders, mutex_interval, ignore_mutex=ignore_mutex, watch=watch))
    except KeyboardInterrupt:
        print('Bye!')


async def _run_folder_tasks(
        folders: Iterable[Folder],
        mutex_interval: float, ignore_mutex: bool = False, watch: bool = True) -> None:
    mutexes: dict[str, Mutex] = {}
    try:
        if not ignore_mutex:
            summary = _get_summary(folders)
            mutexes = {folder.host: Mutex(folder.host, folder.ssh_port, mutex_interval) for folder in folders}
            for mutex in mutexes.values():
                print(f'Checking mutex on {mutex.host}', flush=True)
                if not await mutex.set(summary):
                    print(f'Target is in use by {mutex.occupant}')
                    sys.exit(1)

        for folder in folders:
            print(f'  {folder.source_path} --> {folder.target}', flush=True)
            await folder.sync()

        if watch:
            tasks: list[tuple[Folder, asyncio.Task]] = []
            for folder in folders:
                print(f'Watch folder {folder.source_path}', flush=True)
                tasks.append((folder, asyncio.create_task(folder.watch())))

            while True:
                if not ignore_mutex:
                    tasks = await _renew_mutexes(folders, mutexes, tasks)
                    if not tasks:
                        print('No more folders to watch, exiting', flush=True)
                        break
                await asyncio.sleep(mutex_interval)
    except Exception as e:  # noqa: BLE001  # report any failure and still release the mutexes below
        print(e)
    finally:
        # NOTE: release the mutexes we still hold, also on Ctrl+C (asyncio cancels this task) and after a one-off sync,
        # so that the target does not stay locked until the expiry
        for mutex in mutexes.values():
            await mutex.release()


async def _renew_mutexes(
    folders: Iterable[Folder],
    mutexes: dict[str, Mutex],
    tasks: list[tuple[Folder, asyncio.Task]],
) -> list[tuple[Folder, asyncio.Task]]:
    summary = _get_summary(folders)
    for host in list(mutexes):
        if await mutexes[host].set(summary):
            continue
        print(f'Target {host} is in use by {mutexes[host].occupant}, stopping watch tasks', flush=True)
        for folder, task in tasks:
            if folder.host == host:
                task.cancel()
        tasks = [(folder, task) for folder, task in tasks if folder.host != host]
        del mutexes[host]
    return tasks


def _get_summary(folders: Iterable[Folder]) -> str:
    return '\n'.join(folder.get_summary() for folder in folders).replace('"', "'")

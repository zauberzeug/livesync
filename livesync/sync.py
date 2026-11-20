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
    tasks: list[tuple[Folder, asyncio.Task]] = []
    try:
        if not ignore_mutex:
            summary = _get_summary(folders)
            mutexes = {folder.host: Mutex(folder.host, folder.ssh_port, mutex_interval) for folder in folders}
            for mutex in mutexes.values():
                print(f'Checking mutex on {mutex.host}', flush=True)
                if not await mutex.set(summary):
                    print(f'Target is in use by {mutex.occupant}')
                    sys.exit(1)

        # NOTE: the folders sync and watch in tasks of their own, so that the mutexes are renewed on time
        # even while an initial sync takes longer than the expiry (large repository, slow link)
        initial_sync_lock = asyncio.Lock()
        tasks = [(folder, asyncio.create_task(_sync_folder(folder, initial_sync_lock, watch=watch)))
                 for folder in folders]
        renewal_duration = 0.0
        while tasks:
            # NOTE: subtract the duration of the last renewal (git summary and ssh round trips),
            # so that the mutex is written every mutex_interval seconds and stays within the expiry
            await asyncio.wait([task for _, task in tasks], timeout=max(0.0, mutex_interval - renewal_duration))
            for _, task in tasks:
                if task.done():
                    task.result()  # NOTE: re-raise the exception of a failed sync
            tasks = [(folder, task) for folder, task in tasks if not task.done()]
            if tasks and not ignore_mutex:
                renewal_start = asyncio.get_running_loop().time()
                tasks = await _renew_mutexes(folders, mutexes, tasks)
                renewal_duration = asyncio.get_running_loop().time() - renewal_start
                if not tasks:
                    print('No more folders to watch, exiting', flush=True)
    except Exception as e:  # noqa: BLE001  # report any failure and still release the mutexes below
        print(e)
    finally:
        # NOTE: stop syncing before releasing the mutexes, so that no rsync writes to a target we no longer hold
        for _, task in tasks:
            task.cancel()
        await asyncio.gather(*(task for _, task in tasks), return_exceptions=True)
        # NOTE: release the mutexes we still hold, also on Ctrl+C (asyncio cancels this task) and after a one-off sync,
        # so that the target does not stay locked until the expiry
        for mutex in mutexes.values():
            await mutex.release()


async def _sync_folder(folder: Folder, initial_sync_lock: asyncio.Lock, *, watch: bool) -> None:
    async with initial_sync_lock:  # NOTE: initial syncs run one after the other, in the order of the folders
        print(f'  {folder.source_path} --> {folder.target}', flush=True)
        await folder.sync()
    if watch:
        print(f'Watch folder {folder.source_path}', flush=True)
        await folder.watch()


async def _renew_mutexes(
    folders: Iterable[Folder],
    mutexes: dict[str, Mutex],
    tasks: list[tuple[Folder, asyncio.Task]],
) -> list[tuple[Folder, asyncio.Task]]:
    summary = _get_summary(folders)
    for host in list(mutexes):
        if await mutexes[host].set(summary):
            continue
        print(f'Target {host} is in use by {mutexes[host].occupant}, stopping sync and watch tasks', flush=True)
        for folder, task in tasks:
            if folder.host == host:
                task.cancel()
        tasks = [(folder, task) for folder, task in tasks if folder.host != host]
        del mutexes[host]
    return tasks


def _get_summary(folders: Iterable[Folder]) -> str:
    return '\n'.join(folder.get_summary() for folder in folders).replace('"', "'")

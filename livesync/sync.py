import asyncio
import sys
from collections.abc import Iterable

from .folder import Folder
from .mutex import Mutex


def sync(*folders: Folder, mutex_interval: float = 10, ignore_mutex: bool = False, watch: bool = True) -> None:
    """Synchronize one or more folders, optionally watching for changes.

    If a sync or watch fails, the mutexes are released and the exception is raised.
    """
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
        loop = asyncio.get_running_loop()
        next_renewal = loop.time() + mutex_interval
        while tasks:
            # NOTE: wake up as soon as a task ends, to re-raise its exception or to stop when all are done,
            # otherwise when the next renewal is due; the deadline is absolute and counted from the start of the
            # last renewal, so that its duration (git summary and ssh round trips) does not stretch the time
            # between two writes beyond mutex_interval and the mutex stays within the expiry
            timeout = None if ignore_mutex else max(0.0, next_renewal - loop.time())
            await asyncio.wait([task for _, task in tasks], timeout=timeout, return_when=asyncio.FIRST_COMPLETED)
            for _, task in tasks:
                if task.done():
                    task.result()  # NOTE: re-raise the exception of a failed sync
            tasks = [(folder, task) for folder, task in tasks if not task.done()]
            if tasks and not ignore_mutex and loop.time() >= next_renewal:
                next_renewal = loop.time() + mutex_interval
                tasks = await _renew_mutexes(folders, mutexes, tasks)
            if watch and not tasks:
                print('No more folders to watch, exiting', flush=True)
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
        cancelled = [task for folder, task in tasks if folder.host == host]
        for task in cancelled:
            task.cancel()
        await asyncio.gather(*cancelled, return_exceptions=True)  # NOTE: wait until rsync is killed before going on
        tasks = [(folder, task) for folder, task in tasks if folder.host != host]
        del mutexes[host]
    return tasks


def _get_summary(folders: Iterable[Folder]) -> str:
    return '\n'.join(folder.get_summary() for folder in folders).replace('"', "'")

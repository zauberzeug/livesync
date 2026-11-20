import asyncio
import sys
from collections.abc import Iterable

from .folder import Folder
from .mutex import Mutex

RETRY_INTERVAL = 1.0
'''Seconds between two attempts to renew a mutex after a failed renewal.'''


def sync(*folders: Folder, mutex_interval: float = 10, ignore_mutex: bool = False, watch: bool = True) -> None:
    """Synchronize one or more folders, optionally watching for changes.

    If the initial sync or the watch fails, the mutexes are released and the exception is raised.
    A sync that fails after a change is reported, and the watch goes on.
    If the mutex of a target is lost, its folders stop syncing, and a ``RuntimeError`` is raised once the others are done.
    """
    try:
        asyncio.run(_run_folder_tasks(folders, mutex_interval, ignore_mutex=ignore_mutex, watch=watch))
    except KeyboardInterrupt:
        print('Bye!')


async def _run_folder_tasks(
        folders: Iterable[Folder],
        mutex_interval: float, ignore_mutex: bool = False, watch: bool = True) -> None:
    mutexes: dict[str, Mutex] = {}
    keepers: dict[asyncio.Task, Mutex] = {}
    tasks: list[tuple[Folder, asyncio.Task]] = []
    try:
        if not ignore_mutex:
            summary = _get_summary(folders)
            mutexes = {folder.host: Mutex(folder.host, folder.ssh_port, mutex_interval) for folder in folders}
            loop = asyncio.get_running_loop()
            for mutex in mutexes.values():
                print(f'Checking mutex on {mutex.host}', flush=True)
                start = loop.time()
                if not await _acquire_mutex(mutex, summary):
                    sys.exit(1)
                keepers[asyncio.create_task(_keep_mutex(mutex, folders, mutex_interval, start))] = mutex

        # NOTE: the folders sync and watch in tasks of their own, and each mutex is renewed in a task of its own,
        # so that the mutexes are renewed on time even while an initial sync takes longer than the expiry
        # (large repository, slow link) or while the renewal of another host hangs
        initial_sync_lock = asyncio.Lock()
        tasks = [(folder, asyncio.create_task(_sync_folder(folder, initial_sync_lock, watch=watch)))
                 for folder in folders]
        lost: list[str] = []
        while tasks:
            # NOTE: wake up as soon as a task ends, to re-raise its exception or to stop when all are done,
            # or as soon as a mutex is lost, to stop the tasks of its host
            await asyncio.wait([*(task for _, task in tasks), *keepers], return_when=asyncio.FIRST_COMPLETED)
            for _, task in tasks:
                if task.done():
                    task.result()  # NOTE: re-raise the exception of a failed sync
            tasks = [(folder, task) for folder, task in tasks if not task.done()]
            for keeper in [keeper for keeper in keepers if keeper.done()]:
                mutex = keepers.pop(keeper)
                del mutexes[mutex.host]
                tasks, reason = await _stop_lost_host(tasks, mutex, expired=keeper.result())
                lost.append(reason)
            if watch and not tasks:
                print('No more folders to watch, exiting', flush=True)
        if lost:
            # NOTE: a sync that was cut short is a failure, also for a one-off sync, so the exit status is not 0
            raise RuntimeError('; '.join(lost))
    finally:
        # NOTE: stop syncing before releasing the mutexes, so that no rsync writes to a target we no longer hold
        running = [task for _, task in tasks] + list(keepers)
        for task in running:
            task.cancel()
        await asyncio.gather(*running, return_exceptions=True)
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


async def _acquire_mutex(mutex: Mutex, summary: str) -> bool:
    """Set the mutex and return whether successful, saying why if not."""
    try:
        if await mutex.set(summary):
            return True
        print(f'Target is in use by {mutex.occupant}')
    except RuntimeError as e:
        print(f'Could not reach target {mutex.host}: {e}')
    return False


async def _keep_mutex(mutex: Mutex, folders: Iterable[Folder], interval: float, last_renewal: float) -> bool:
    """Renew the mutex every ``interval`` seconds until it is lost, and return whether it was lost by expiry.

    The mutex is lost if another source holds it, or if it could not be renewed before it expired.
    A renewal that fails (connection drop, DNS hiccup, saturated link) does not mean that another source holds it,
    so it is retried until the expiry.
    ``last_renewal`` is the event loop time at which the mutex was set.
    """
    assert mutex.written_at is not None, 'the mutex must be set before it is kept'
    loop = asyncio.get_running_loop()
    deadline = mutex.written_at + mutex.expiry
    next_renewal = last_renewal + interval
    while True:
        await asyncio.sleep(max(0.0, next_renewal - loop.time()))
        # NOTE: count the next renewal from the start of this one, so that its duration (git summary and ssh round trips)
        # does not stretch the time between two writes beyond the interval
        start = loop.time()
        try:
            # NOTE: a renewal must not write after the expiry, when another source may already have taken over,
            # and a hanging ssh must not keep the tasks running beyond it
            async with asyncio.timeout_at(deadline):
                if not await mutex.set(_get_summary(folders)):
                    print(f'Target {mutex.host} is in use by {mutex.occupant}, stopping sync and watch tasks', flush=True)
                    return False
            deadline = mutex.written_at + mutex.expiry
            next_renewal = start + interval
        except (RuntimeError, TimeoutError) as e:
            if loop.time() >= deadline:
                print(f'Could not renew the mutex on {mutex.host} before it expired, stopping sync and watch tasks',
                      flush=True)
                return True
            print(f'Could not renew the mutex on {mutex.host} ({e}), retrying', flush=True)
            next_renewal = min(loop.time() + min(interval, RETRY_INTERVAL), deadline)


async def _stop_lost_host(
    tasks: list[tuple[Folder, asyncio.Task]],
    mutex: Mutex,
    *,
    expired: bool,
) -> tuple[list[tuple[Folder, asyncio.Task]], str]:
    """Stop the sync and watch tasks of the host whose mutex was lost, and return the remaining tasks and the reason."""
    stopped = [task for folder, task in tasks if folder.host == mutex.host]
    for task in stopped:
        task.cancel()
    await asyncio.gather(*stopped, return_exceptions=True)  # NOTE: wait until rsync is killed before going on
    remaining = [(folder, task) for folder, task in tasks if folder.host != mutex.host]
    if expired:
        # NOTE: the last write may have reached the target although its answer did not reach us
        await mutex.release()
        return remaining, f'The mutex on {mutex.host} expired'
    return remaining, f'Target {mutex.host} is in use by {mutex.occupant}'


def _get_summary(folders: Iterable[Folder]) -> str:
    return '\n'.join(folder.get_summary() for folder in folders).replace('"', "'")

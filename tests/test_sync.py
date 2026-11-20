"""Unit tests for the loop that syncs the folders and renews the mutexes, with fake folders and mutexes."""
import asyncio
import contextlib
import importlib
import itertools
import time
from typing import ClassVar

import pytest

sync_module = importlib.import_module('livesync.sync')  # NOTE: ``livesync.sync`` is shadowed by the function


class FakeFolder:
    """A folder whose initial sync takes ``sync_duration`` seconds and whose watch runs until it is cancelled."""

    def __init__(self, host: str, sync_duration: float = 0.0) -> None:
        self.host = host
        self.ssh_port = 22
        self.source_path = f'/source/{host}'
        self.target = f'{host}:/target'
        self.sync_duration = sync_duration
        self.syncs_finished = 0
        self.sync_cancelled = False
        self.watch_cancelled = False

    def get_summary(self) -> str:
        """Return a summary without git information."""
        return f'{self.source_path} --> {self.target}\n'

    async def sync(self) -> None:
        """Pretend to sync for ``sync_duration`` seconds."""
        try:
            await asyncio.sleep(self.sync_duration)
        except asyncio.CancelledError:
            self.sync_cancelled = True
            raise
        self.syncs_finished += 1

    async def watch(self) -> None:
        """Watch until cancelled."""
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            self.watch_cancelled = True
            raise


class FakeMutex:
    """A mutex that records when it is set and released, and can be taken over by another source."""
    instances: ClassVar[dict[str, 'FakeMutex']] = {}

    def __init__(self, host: str, port: int, interval: float = 10) -> None:
        self.host = host
        self.occupant: str | None = None
        self.set_times: list[float] = []
        self.released = False
        self.taken_over = False
        self.set_duration = 0.0
        FakeMutex.instances[host] = self

    async def set(self, info: str) -> bool:
        """Record the time and succeed unless another source has taken the mutex over."""
        await asyncio.sleep(self.set_duration)
        self.set_times.append(asyncio.get_running_loop().time())
        if self.taken_over:
            self.occupant = 'other'
            return False
        return True

    async def release(self) -> None:
        """Record the release."""
        self.released = True


@pytest.fixture(autouse=True)
def fake_mutex(monkeypatch: pytest.MonkeyPatch) -> None:
    """Replace the mutex by a fake one for every test."""
    FakeMutex.instances = {}
    monkeypatch.setattr(sync_module, 'Mutex', FakeMutex)


def run(folders: list[FakeFolder], *, watch: bool, timeout: float = 1.0, interval: float = 0.05, **kwargs) -> None:
    """Run the loop until it ends by itself or ``timeout`` seconds have passed (like Ctrl+C)."""
    async def main() -> None:
        with contextlib.suppress(TimeoutError):
            await asyncio.wait_for(sync_module._run_folder_tasks(folders, interval, watch=watch, **kwargs), timeout)
    asyncio.run(main())


def test_mutex_is_renewed_during_long_initial_sync() -> None:
    """An initial sync that takes longer than the expiry must not leave the target unprotected."""
    folder = FakeFolder('a', sync_duration=0.3)
    run([folder], watch=False)
    mutex = FakeMutex.instances['a']
    assert folder.syncs_finished == 1
    assert len(mutex.set_times) >= 4, 'the mutex must be renewed every interval while the initial sync is running'
    assert max(b - a for a, b in itertools.pairwise(mutex.set_times)) < 0.15
    assert mutex.released


def test_renewal_duration_does_not_delay_next_renewal(monkeypatch: pytest.MonkeyPatch) -> None:
    """A slow renewal (git summary, ssh round trips) must not stretch the time between two writes beyond the interval."""
    class SlowMutex(FakeMutex):
        """A mutex whose renewal takes most of the interval."""

        def __init__(self, *args, **kwargs) -> None:
            super().__init__(*args, **kwargs)
            self.set_duration = 0.08
    monkeypatch.setattr(sync_module, 'Mutex', SlowMutex)
    run([FakeFolder('a')], watch=True, timeout=1.0, interval=0.1)
    times = FakeMutex.instances['a'].set_times
    assert len(times) >= 6
    assert max(b - a for a, b in itertools.pairwise(times[1:])) < 0.14


def test_initial_syncs_run_one_after_the_other() -> None:
    """The initial syncs keep their order and do not run in parallel."""
    folders = [FakeFolder('a', sync_duration=0.1), FakeFolder('a', sync_duration=0.1)]
    folders[1].source_path = '/source/b'
    order: list[str] = []
    for folder in folders:
        original = folder.sync

        async def sync(folder: FakeFolder = folder, original=original) -> None:
            order.append(f'start {folder.source_path}')
            await original()
            order.append(f'end {folder.source_path}')
        folder.sync = sync  # type: ignore[method-assign]
    run(folders, watch=False)
    assert order == ['start /source/a', 'end /source/a', 'start /source/b', 'end /source/b']


def test_lost_mutex_stops_sync_of_its_host_only() -> None:
    """Losing the mutex of one host stops its initial sync, while the other host keeps syncing and watching."""
    folders = [FakeFolder('a', sync_duration=0.5), FakeFolder('b')]

    async def take_over() -> None:
        await asyncio.sleep(0.02)
        FakeMutex.instances['a'].taken_over = True

    async def main() -> None:
        asyncio.get_running_loop().create_task(take_over())
        with contextlib.suppress(TimeoutError):
            await asyncio.wait_for(sync_module._run_folder_tasks(folders, 0.05, watch=True), 0.3)
    asyncio.run(main())
    assert folders[0].sync_cancelled, 'the initial sync to a lost target must be stopped'
    assert folders[1].syncs_finished == 1
    assert folders[1].watch_cancelled, 'the other folder keeps watching until the loop is cancelled'
    assert 'a' in FakeMutex.instances and not FakeMutex.instances['a'].released
    assert FakeMutex.instances['b'].released


def test_tasks_are_stopped_before_mutex_is_released() -> None:
    """When the loop is cancelled (like Ctrl+C), the watch tasks are stopped and the mutex is released."""
    folder = FakeFolder('a')
    run([folder], watch=True, timeout=0.2)
    assert folder.watch_cancelled
    assert FakeMutex.instances['a'].released


def test_ignore_mutex_syncs_without_mutex() -> None:
    """With ``ignore_mutex`` the folders sync without creating any mutex."""
    folder = FakeFolder('a', sync_duration=0.1)
    run([folder], watch=False, ignore_mutex=True)
    assert folder.syncs_finished == 1
    assert not FakeMutex.instances


def test_failed_initial_sync_stops_the_others_immediately() -> None:
    """A failed initial sync raises right away, before the next folder gets far with its own sync."""
    class FailingFolder(FakeFolder):
        """A folder whose sync fails."""

        async def sync(self) -> None:
            raise RuntimeError('rsync failed')
    folders = [FailingFolder('a'), FakeFolder('a', sync_duration=0.2)]
    start = time.monotonic()
    with pytest.raises(RuntimeError, match='rsync failed'):
        asyncio.run(sync_module._run_folder_tasks(folders, 0.5, watch=False))
    assert time.monotonic() - start < 0.1, 'the failure must not wait for the next renewal'
    assert folders[1].sync_cancelled
    assert FakeMutex.instances['a'].released


def test_failed_watch_raises_after_cleanup() -> None:
    """A failed watch task ends the loop with its exception, after the other tasks are stopped and the mutex is released."""
    class FailingWatchFolder(FakeFolder):
        """A folder whose watch fails after a moment."""

        async def watch(self) -> None:
            await asyncio.sleep(0.02)
            raise RuntimeError('watch failed')
    folders = [FailingWatchFolder('a'), FakeFolder('b')]
    with pytest.raises(RuntimeError, match='watch failed'):
        asyncio.run(sync_module._run_folder_tasks(folders, 0.05, watch=True))
    assert folders[1].watch_cancelled
    assert FakeMutex.instances['a'].released
    assert FakeMutex.instances['b'].released


def test_watch_that_ends_by_itself_ends_the_loop_with_a_message(capsys: pytest.CaptureFixture[str]) -> None:
    """When the last watch task ends normally, the loop ends and says so instead of exiting silently."""
    class EndingWatchFolder(FakeFolder):
        """A folder whose watch returns after a moment, like after watchfiles' "Already borrowed"."""

        async def watch(self) -> None:
            await asyncio.sleep(0.02)
    folder = EndingWatchFolder('a')
    start = time.monotonic()
    run([folder], watch=True, timeout=1.0)
    assert time.monotonic() - start < 0.5, 'the loop must end by itself, not by the timeout'
    assert 'No more folders to watch' in capsys.readouterr().out
    assert FakeMutex.instances['a'].released

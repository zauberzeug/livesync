"""Unit tests for ``Mutex`` against a fake ``ssh`` that runs the remote command locally."""
import asyncio
import os
import shutil
import time
from collections.abc import Iterator
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from livesync.mutex import Mutex


@pytest.fixture(params=['sh', 'dash', 'fish', 'tcsh'])
def remote(request: pytest.FixtureRequest, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    """Put a fake ``ssh`` on PATH whose remote home is a temporary folder, and run in UTC until the test is over.

    The remote command runs in the login shell of the parameter (skipped if it is not installed),
    since the target's login shell interprets it and need not be POSIX.
    """
    shell = request.param
    if shutil.which(shell) is None:
        pytest.skip(f'{shell} is not installed')
    home = tmp_path / 'home'
    home.mkdir()
    ssh = tmp_path / 'bin' / 'ssh'
    ssh.parent.mkdir()
    ssh.write_text(f'#!/bin/sh\nHOME="{home}" exec {shell} -c "$4"\n')  # ssh HOST -p PORT COMMAND
    ssh.chmod(0o755)
    monkeypatch.setenv('PATH', f'{ssh.parent}{os.pathsep}{os.environ["PATH"]}')
    original_tz = os.environ.get('TZ')
    set_tz('UTC')
    yield home
    set_tz(original_tz)  # NOTE: monkeypatch would restore the variable, but not the time zone the process computes with


def set_tz(tz: str | None) -> None:
    """Switch the process to the time zone ``tz`` (``None`` for the system default)."""
    if tz is None:
        os.environ.pop('TZ', None)
    else:
        os.environ['TZ'] = tz
    time.tzset()


def acquire(user_id: str, tz: str, interval: float = 10) -> bool:
    """Try to set the mutex as ``user_id`` on a source whose local time zone is ``tz`` and that renews every ``interval``."""
    set_tz(tz)
    mutex = Mutex('target', 22, interval)
    mutex.user_id = user_id
    return asyncio.run(mutex.set('info'))


def release(user_id: str) -> None:
    """Release the mutex as ``user_id``."""
    mutex = Mutex('target', 22)
    mutex.user_id = user_id
    asyncio.run(mutex.release())


def age_mutex(path: Path, seconds: float) -> None:
    """Backdate both the written timestamp and the file's mtime, so the test does not depend on which one is read."""
    first_line, rest = path.read_text().split('\n', 1)
    user_id, _, *more = first_line.split()
    timestamp = (datetime.now() - timedelta(seconds=seconds)).isoformat()
    path.write_text(' '.join([user_id, timestamp, *more]) + f'\n{rest}')
    stale = time.time() - seconds
    os.utime(path, (stale, stale))


@pytest.mark.parametrize('tz_a, tz_b', [('UTC', 'UTC'), ('UTC', 'Europe/Berlin'), ('Europe/Berlin', 'UTC')])
def test_mutex_across_time_zones(remote: Path, tz_a: str, tz_b: str) -> None:
    """The mutex age must not depend on the time zones of the two sources."""
    assert acquire('A', tz_a)
    assert not acquire('B', tz_b), 'a fresh mutex of another source must block'

    age_mutex(remote / '.livesync_mutex', seconds=20)
    assert acquire('B', tz_b), 'an expired mutex must be free'


def test_long_interval_extends_expiry(remote: Path) -> None:
    """A holder with a long renewal interval must stay protected between two renewals, whatever the other's interval."""
    assert acquire('A', 'UTC', interval=30)
    age_mutex(remote / '.livesync_mutex', seconds=20)
    assert not acquire('B', 'UTC', interval=10), 'the mutex must last longer than the interval of its holder'

    age_mutex(remote / '.livesync_mutex', seconds=50)
    assert acquire('B', 'UTC', interval=10), 'the mutex must expire after 1.5 times the interval of its holder'


def test_mutex_without_expiry_expires_after_default(remote: Path) -> None:
    """A mutex written by an older version without expiry must still expire after 15 s."""
    path = remote / '.livesync_mutex'
    path.write_text(f'A {datetime.now().isoformat()}\ninfo\n')
    assert not acquire('B', 'UTC', interval=30), 'a fresh mutex of an older version must block'

    age_mutex(path, seconds=20)
    assert acquire('B', 'UTC', interval=30), 'without expiry, the default of 15 s must apply'


def test_release_frees_mutex_immediately(remote: Path) -> None:
    """A released mutex must be free at once, however long its expiry would have been."""
    assert acquire('A', 'UTC', interval=30)
    release('A')
    assert not (remote / '.livesync_mutex').exists(), 'the holder must remove its mutex file'
    assert acquire('B', 'UTC'), 'a released mutex must be free'


def test_release_keeps_mutex_of_other_source(remote: Path) -> None:
    """Releasing must not remove a mutex that another source has taken over meanwhile."""
    assert acquire('A', 'UTC')
    age_mutex(remote / '.livesync_mutex', seconds=20)
    assert acquire('B', 'UTC'), 'an expired mutex must be free'
    release('A')
    assert (remote / '.livesync_mutex').exists(), 'the mutex of another source must stay'
    assert not acquire('A', 'UTC'), 'the other source must still hold the mutex'


def test_release_without_mutex_file(remote: Path) -> None:
    """Releasing without a mutex file must not fail."""
    release('A')
    assert not (remote / '.livesync_mutex').exists()


def test_empty_mutex_is_free(remote: Path) -> None:
    """An empty mutex file must still count as free."""
    assert acquire('A', 'UTC')
    (remote / '.livesync_mutex').write_text('')
    assert acquire('B', 'UTC')


def test_symlinked_mutex_is_renewed(remote: Path) -> None:
    """Writing through a symlink must count as renewing the mutex, i.e. the age is that of the file behind the link."""
    assert acquire('A', 'UTC')
    path = remote / '.livesync_mutex'
    path.rename(remote / 'real_mutex')
    path.symlink_to(remote / 'real_mutex')
    stale = time.time() - 20
    os.utime(path, (stale, stale), follow_symlinks=False)
    assert acquire('A', 'UTC'), 'the holder must be able to renew'
    assert not acquire('B', 'UTC'), 'a mutex renewed through a symlink must still block'


def test_missing_stat_blocks_other_sources(remote: Path) -> None:
    """Without ``stat`` on the target, the holder can still renew, but other sources must read the mutex as busy."""
    stat = remote.parent / 'bin' / 'stat'  # NOTE: shadows the real stat on the PATH of the fake ssh
    stat.write_text('#!/bin/sh\nexit 1\n')
    stat.chmod(0o755)
    assert acquire('A', 'UTC')
    assert acquire('A', 'UTC'), 'the holder must be able to renew'
    assert not acquire('B', 'UTC'), 'an age that cannot be determined must not count as expired'


def test_expiry_is_a_whole_number_of_seconds() -> None:
    """The age is measured in whole seconds, so a fractional expiry would let another source take over early."""
    assert Mutex('target', 22, 10).expiry == 15
    assert Mutex('target', 22, 11).expiry == 17


def test_unreachable_target_raises(remote: Path) -> None:
    """A failed ssh round trip must raise instead of reporting the mutex as held by another source."""
    ssh = remote.parent / 'bin' / 'ssh'
    ssh.write_text('#!/bin/sh\nexit 255\n')
    with pytest.raises(RuntimeError, match='return code 255'):
        acquire('A', 'UTC')

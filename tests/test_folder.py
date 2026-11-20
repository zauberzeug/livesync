import asyncio
import subprocess
from pathlib import Path

import pytest
import watchfiles

from livesync import Folder
from livesync.folder import _quote_remote_path


def test_invalid_source_path_raises(tmp_path: Path) -> None:
    """A source path that is not a directory raises an exception the caller can handle instead of exiting."""
    file = tmp_path / 'file.txt'
    file.write_text('not a folder')
    with pytest.raises(NotADirectoryError, match=r'file\.txt'):
        Folder(file, 'robot:~/project')
    with pytest.raises(NotADirectoryError, match='missing'):
        Folder(tmp_path / 'missing', 'robot:~/project')


@pytest.mark.parametrize(('path', 'quoted'), [
    ('~', '~'),
    ('~/x y', "~/'x y'"),
    ('~user', '~user'),
    ('~user/x y', "~user/'x y'"),
    ('/a b', "'/a b'"),
    ("/a'b", "'/a'\"'\"'b'"),
    ('plain', 'plain'),
])
def test_quote_remote_path(path: str, quoted: str) -> None:
    """A leading ``~`` or ``~user`` stays unquoted for the remote shell to expand, everything else is quoted."""
    assert _quote_remote_path(path) == quoted


def test_failed_sync_after_change_keeps_watching(tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
                                                 capsys: pytest.CaptureFixture[str]) -> None:
    """A sync that fails after a change is reported, and the next change syncs again instead of ending the watch."""
    async def fake_awatch(*_args, **_kwargs):
        yield {(watchfiles.Change.modified, str(tmp_path / 'a.txt'))}
        yield {(watchfiles.Change.modified, str(tmp_path / 'b.txt'))}
    monkeypatch.setattr(watchfiles, 'awatch', fake_awatch)
    folder = Folder(tmp_path, 'robot:~/project')
    results = [subprocess.CalledProcessError(24, 'rsync'), None]
    syncs: list[int] = []

    async def sync() -> None:
        syncs.append(1)
        result = results.pop(0)
        if result is not None:
            raise result
    monkeypatch.setattr(folder, 'sync', sync)
    asyncio.run(folder.watch())
    assert len(syncs) == 2, 'the second change must be synced although the first sync failed'
    assert 'failed with exit status 24, waiting for the next change' in capsys.readouterr().out

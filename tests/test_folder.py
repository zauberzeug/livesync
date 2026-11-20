from pathlib import Path

import pytest

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

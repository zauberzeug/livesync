from pathlib import Path

import pytest

from livesync import Folder


def test_invalid_source_path_raises(tmp_path: Path) -> None:
    """A source path that is not a directory raises an exception the caller can handle instead of exiting."""
    file = tmp_path / 'file.txt'
    file.write_text('not a folder')
    with pytest.raises(NotADirectoryError, match=r'file\.txt'):
        Folder(file, 'robot:~/project')
    with pytest.raises(NotADirectoryError, match='missing'):
        Folder(tmp_path / 'missing', 'robot:~/project')

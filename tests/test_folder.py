from pathlib import Path

import pytest

from livesync import Folder


def test_invalid_source_path_raises(tmp_path: Path) -> None:
    file = tmp_path / 'file.txt'
    file.write_text('not a folder')
    with pytest.raises(NotADirectoryError, match='file.txt'):
        Folder(file, 'robot:~/project')
    with pytest.raises(NotADirectoryError, match='missing'):
        Folder(tmp_path / 'missing', 'robot:~/project')

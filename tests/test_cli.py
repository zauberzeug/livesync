"""Unit tests for the command-line interface."""
import sys
from pathlib import Path

import pytest

from livesync import livesync as cli


@pytest.fixture
def argv(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Call the CLI with a valid source folder."""
    monkeypatch.setattr(sys, 'argv', ['livesync', str(tmp_path), 'robot:~/project'])


def test_expected_failure_ends_with_message_and_status_1(argv: None, monkeypatch: pytest.MonkeyPatch,
                                                         capsys: pytest.CaptureFixture[str]) -> None:
    """A lost mutex or a failed sync ends with a short message and exit status 1."""
    def sync(*_args, **_kwargs) -> None:
        raise RuntimeError('Target robot is in use by other')
    monkeypatch.setattr(cli, 'sync', sync)
    with pytest.raises(SystemExit, match='1'):
        cli.main()
    assert capsys.readouterr().out.strip() == 'Target robot is in use by other'


def test_unexpected_failure_keeps_its_traceback(argv: None, monkeypatch: pytest.MonkeyPatch) -> None:
    """A bug in LiveSync is not reduced to its message, so that a report can include the traceback."""
    def sync(*_args, **_kwargs) -> None:
        raise KeyError('host')
    monkeypatch.setattr(cli, 'sync', sync)
    with pytest.raises(KeyError):
        cli.main()

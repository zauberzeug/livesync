"""Unit tests for ``run_subprocess``."""
import asyncio
import os
from pathlib import Path

import pytest

from livesync.run_subprocess import run_subprocess


def test_cancel_kills_the_command_itself(tmp_path: Path) -> None:
    """Cancelling must kill the command, not only the shell that started it (dash would fork a plain command)."""
    pid_file = tmp_path / 'pid'

    async def main() -> int:
        task = asyncio.create_task(run_subprocess(f"sh -c 'echo $$ > {pid_file}; exec sleep 10'"))
        while not pid_file.exists() or not pid_file.read_text().strip():  # noqa: ASYNC110  # written by another process
            await asyncio.sleep(0.01)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        return int(pid_file.read_text())
    pid = asyncio.run(main())
    with pytest.raises(ProcessLookupError):
        os.kill(pid, 0)

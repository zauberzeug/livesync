"""Unit tests for ``run_subprocess``."""
import asyncio
import time

import pytest

from livesync.run_subprocess import run_subprocess


def test_cancel_kills_the_children_of_the_command() -> None:
    """Cancelling must end at once, although a child of the command (like the ssh started by rsync) holds the output pipe."""
    async def main() -> float:
        task = asyncio.create_task(run_subprocess("sh -c 'sleep 10 & exec sleep 10'"))
        await asyncio.sleep(0.2)
        task.cancel()
        start = time.monotonic()
        with pytest.raises(asyncio.CancelledError):
            await task
        return time.monotonic() - start
    assert asyncio.run(main()) < 1.0, 'waiting for the process must not wait for the child to let go of the pipe'

import asyncio
import contextlib
import os
import signal
import subprocess


async def run_subprocess(command: str, *, quiet: bool = False) -> None:
    """Run a single command asynchronously, capturing its output and raising an exception on failure."""
    # NOTE: `exec` replaces the shell by the command, so that the kill below reaches the command itself;
    # dash (the /bin/sh of Debian and Ubuntu) would otherwise fork it and leave it running as an orphan.
    # This is why `command` must be a single command, not a pipe or a chain.
    # The command runs in a session of its own, so that the kill also reaches its children (rsync starts ssh):
    # they inherit our output pipe, and `process.wait()` only returns once every holder of the pipe is gone.
    process = await asyncio.create_subprocess_shell(
        f'exec {command}',
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
        start_new_session=True,
    )
    try:
        stdout, _ = await process.communicate()
    except asyncio.CancelledError:
        # NOTE: a cancelled sync must not keep writing to the target, e.g. after the mutex was lost
        if process.returncode is None:
            with contextlib.suppress(ProcessLookupError):  # the group may have ended since the check
                os.killpg(process.pid, signal.SIGKILL)
            await process.wait()
        raise
    assert process.returncode is not None  # the process has terminated after communicate()
    if process.returncode != 0:
        print(stdout.decode())
        raise subprocess.CalledProcessError(process.returncode, command, stdout)
    if not quiet:
        print(stdout.decode())

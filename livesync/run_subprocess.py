import asyncio
import contextlib
import subprocess


async def run_subprocess(command: str, *, quiet: bool = False) -> None:
    """Run a single command asynchronously, capturing its output and raising an exception on failure."""
    # NOTE: `exec` replaces the shell by the command, so that the kill below reaches the command itself;
    # dash (the /bin/sh of Debian and Ubuntu) would otherwise fork it and leave it running as an orphan.
    # This is why `command` must be a single command, not a pipe or a chain.
    process = await asyncio.create_subprocess_shell(
        f'exec {command}',
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    try:
        stdout, _ = await process.communicate()
    except asyncio.CancelledError:
        # NOTE: a cancelled sync must not keep writing to the target, e.g. after the mutex was lost
        if process.returncode is None:
            process.kill()
            # NOTE: `wait()` returns only once every holder of the output pipe is gone, and the ssh started by rsync
            # inherits it; it ends by itself once rsync is dead, but on a dead link it may linger, so do not wait for it
            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(process.wait(), timeout=1.0)
        raise
    assert process.returncode is not None  # the process has terminated after communicate()
    if process.returncode != 0:
        print(stdout.decode())
        raise subprocess.CalledProcessError(process.returncode, command, stdout)
    if not quiet:
        print(stdout.decode())

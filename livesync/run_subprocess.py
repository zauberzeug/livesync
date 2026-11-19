import asyncio
import subprocess


async def run_subprocess(command: str, *, quiet: bool = False) -> None:
    """Run a subprocess asynchronously, capturing its output and raising an exception on failure."""
    process = await asyncio.create_subprocess_shell(
        command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    try:
        stdout, _ = await process.communicate()
    except asyncio.CancelledError:
        # NOTE: a cancelled sync must not keep writing to the target, e.g. after the mutex was lost
        if process.returncode is None:
            process.kill()
            await process.wait()
        raise
    assert process.returncode is not None  # the process has terminated after communicate()
    if process.returncode != 0:
        print(stdout.decode())
        raise subprocess.CalledProcessError(process.returncode, command, stdout)
    if not quiet:
        print(stdout.decode())

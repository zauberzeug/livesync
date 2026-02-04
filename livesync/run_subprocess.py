import asyncio
import subprocess


async def run_subprocess(command: str, *, quiet: bool = False) -> None:
    process = await asyncio.create_subprocess_shell(
        command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    stdout, _ = await process.communicate()
    if process.returncode != 0:
        print(stdout.decode())
        raise subprocess.CalledProcessError(process.returncode, command, stdout)
    if not quiet:
        print(stdout.decode())

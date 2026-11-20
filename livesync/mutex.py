import asyncio
import logging
import math
import socket
from datetime import datetime

log = logging.getLogger(__name__)


class Mutex:
    """A simple mutex mechanism to prevent concurrent synchronization to the same target host."""
    DEFAULT_FILEPATH = '~/.livesync_mutex'
    DEFAULT_EXPIRY = 15.0

    def __init__(self, host: str, port: int, interval: float = 10) -> None:
        self.host = host
        self.port = port
        # NOTE: whole seconds, since other sources measure the age in whole seconds (`date +%s` minus mtime)
        # and would see a fractional expiry as passed up to a second early
        self.expiry = math.ceil(max(self.DEFAULT_EXPIRY, 1.5 * interval))
        self.occupant: str | None = None
        self.written_at: float | None = None
        '''Event loop time at which the last successful write started, so that the mutex lasts at least until then plus the expiry.'''
        self.user_id = socket.gethostname()

    @property
    def tag(self) -> str:
        """Unique tag for this mutex, based on the user ID, current timestamp and expiry in seconds."""
        # NOTE: the expiry travels with the file, since other sources do not know our renewal interval;
        # older versions only read the first two words and ignore it
        return f'{self.user_id} {datetime.now().isoformat()} {self.expiry:g}'

    async def set(self, info: str) -> bool:
        """Attempt to set the mutex on the target host with the given info and return whether successful.

        Return ``False`` if another source holds the mutex.
        Raise ``RuntimeError`` if the target cannot be reached or the mutex file cannot be written,
        since this does not mean that another source holds the mutex.
        """
        if not await self._is_free():
            return False
        written_at = asyncio.get_running_loop().time()
        # NOTE: pass the content via stdin so the remote shell does not interpret it
        await self._run_ssh_command(f'cat > {self.DEFAULT_FILEPATH}', stdin=f'{self.tag}\n{info}\n')
        self.written_at = written_at
        return True

    async def release(self) -> None:
        """Remove the mutex file from the target host, unless another source has taken it over meanwhile."""
        try:
            # NOTE: give up after the expiry, so that an unreachable target does not block the exit
            async with asyncio.timeout(self.expiry):
                path = self.DEFAULT_FILEPATH
                content = await self._run_ssh_command(f'[ -f {path} ] && cat {path} || echo')
                if content.split()[:1] == [self.user_id]:
                    await self._run_ssh_command(f'rm -f {path}')
        except Exception:
            log.exception('Could not release the mutex on the target system')

    async def _is_free(self) -> bool:
        """Return whether the mutex is free or ours, and raise ``RuntimeError`` if the target cannot be reached."""
        # NOTE: measure the age on the target's clock, since the clocks or time zones of two sources may differ;
        # the target prints its clock and the file's mtime (GNU or BSD stat) and we subtract them here,
        # so that the command also runs in login shells without POSIX arithmetic like fish or csh;
        # the trailing "|| echo" keeps the file content on the third line even if there is no stat at all
        path = self.DEFAULT_FILEPATH
        command = f'date +%s; stat -L -c %Y {path} || stat -L -f %m {path} || echo; [ -f {path} ] && cat {path} || echo'
        lines = (await self._run_ssh_command(command)).strip().splitlines()
        if len(lines) < 3:
            return True
        words = lines[2].split()
        self.occupant = words[0]
        if self.occupant == self.user_id:
            return True
        if not lines[1]:
            log.error('Could not determine the age of the mutex on the target system (is "stat" installed?)')
            return False
        try:
            return int(lines[0]) - int(lines[1]) > self._parse_expiry(words)
        except ValueError:
            log.error('Could not read the age of the mutex on the target system')
            return False

    def _parse_expiry(self, words: list[str]) -> float:
        """Read the expiry written by the occupant, falling back to the default for files of older versions."""
        try:
            return float(words[2])
        except (IndexError, ValueError):
            return self.DEFAULT_EXPIRY

    async def _run_ssh_command(self, command: str, stdin: str | None = None) -> str:
        process = await asyncio.create_subprocess_exec(
            'ssh', self.host, '-p', str(self.port), command,
            stdin=asyncio.subprocess.PIPE if stdin is not None else None,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )
        try:
            stdout, _ = await process.communicate(stdin.encode() if stdin is not None else None)
        except asyncio.CancelledError:
            # NOTE: a renewal that runs into its timeout must not leave a hanging ssh behind
            if process.returncode is None:
                process.kill()
                await process.wait()
            raise
        if process.returncode != 0:
            raise RuntimeError(f'SSH command failed with return code {process.returncode}')
        return stdout.decode()

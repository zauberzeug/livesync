import asyncio
import logging
import socket
from datetime import datetime
from typing import List, Optional


class Mutex:
    """A simple mutex mechanism to prevent concurrent synchronization to the same target host."""
    DEFAULT_FILEPATH = '~/.livesync_mutex'
    DEFAULT_EXPIRY = 15.0

    def __init__(self, host: str, port: int, interval: float = 10) -> None:
        self.host = host
        self.port = port
        self.expiry = max(self.DEFAULT_EXPIRY, 1.5 * interval)
        self.occupant: Optional[str] = None
        self.user_id = socket.gethostname()

    @property
    def tag(self) -> str:
        """Unique tag for this mutex, based on the user ID, current timestamp and expiry in seconds."""
        # NOTE: the expiry travels with the file, since other sources do not know our renewal interval;
        # older versions only read the first two words and ignore it
        return f'{self.user_id} {datetime.now().isoformat()} {self.expiry:g}'

    async def set(self, info: str) -> bool:
        """Attempt to set the mutex on the target host with the given info and return whether successful."""
        if not await self._is_free():
            return False
        try:
            # NOTE: pass the content via stdin so the remote shell does not interpret it
            await self._run_ssh_command(f'cat > {self.DEFAULT_FILEPATH}', stdin=f'{self.tag}\n{info}\n')
            return True
        except RuntimeError:
            print('Could not write mutex file')
            return False

    async def _is_free(self) -> bool:
        try:
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
                logging.error('Could not determine the age of the mutex on the target system (is "stat" installed?)')
                return False
            return int(lines[0]) - int(lines[1]) > self._parse_expiry(words)
        except Exception:  # pylint: disable=broad-except
            logging.exception('Could not access target system')
            return False

    def _parse_expiry(self, words: List[str]) -> float:
        """Read the expiry written by the occupant, falling back to the default for files of older versions."""
        try:
            return float(words[2])
        except (IndexError, ValueError):
            return self.DEFAULT_EXPIRY

    async def _run_ssh_command(self, command: str, stdin: Optional[str] = None) -> str:
        process = await asyncio.create_subprocess_exec(
            'ssh', self.host, '-p', str(self.port), command,
            stdin=asyncio.subprocess.PIPE if stdin is not None else None,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )
        stdout, _ = await process.communicate(stdin.encode() if stdin is not None else None)
        if process.returncode != 0:
            raise RuntimeError(f'SSH command failed with return code {process.returncode}')
        return stdout.decode()

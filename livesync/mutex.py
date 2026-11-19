import asyncio
import logging
import socket
from datetime import datetime
from typing import Optional


class Mutex:
    """A simple mutex mechanism to prevent concurrent synchronization to the same target host."""
    DEFAULT_FILEPATH = '~/.livesync_mutex'

    def __init__(self, host: str, port: int) -> None:
        self.host = host
        self.port = port
        self.occupant: Optional[str] = None
        self.user_id = socket.gethostname()

    @property
    def tag(self) -> str:
        """Unique tag for this mutex, based on the user ID and current timestamp."""
        return f'{self.user_id} {datetime.now().isoformat()}'

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
            # NOTE: measure the age on the target's clock, since the clocks or time zones of two sources may differ
            path = self.DEFAULT_FILEPATH
            age = f'$(( $(date +%s) - $(stat -L -c %Y {path} 2>/dev/null || stat -L -f %m {path}) ))'
            command = f'[ -f {path} ] && echo {age} && cat {path} || echo'
            lines = (await self._run_ssh_command(command)).strip().splitlines()
            if len(lines) < 2:
                return True
            self.occupant = lines[1].split()[0]
            return self.occupant == self.user_id or int(lines[0]) > 15
        except Exception:  # pylint: disable=broad-except
            logging.exception('Could not access target system')
            return False

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

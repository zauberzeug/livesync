import asyncio
import logging
import socket
from datetime import datetime, timedelta
from typing import Optional


class Mutex:
    DEFAULT_FILEPATH = '~/.livesync_mutex'

    def __init__(self, host: str, port: int) -> None:
        self.host = host
        self.port = port
        self.occupant: Optional[str] = None
        self.user_id = socket.gethostname()

    async def is_free(self) -> bool:
        try:
            command = f'[ -f {self.DEFAULT_FILEPATH} ] && cat {self.DEFAULT_FILEPATH} || echo'
            output = (await self._run_ssh_command(command)).strip()
            if not output:
                return True
            words = output.splitlines()[0].strip().split()
            self.occupant = words[0]
            occupant_ok = self.occupant == self.user_id
            mutex_datetime = datetime.fromisoformat(words[1])
            mutex_expired = datetime.now() - mutex_datetime > timedelta(seconds=15)
            return occupant_ok or mutex_expired
        except Exception:
            logging.exception('Could not access target system')
            return False

    async def set(self, info: str) -> bool:
        if not await self.is_free():
            return False
        try:
            await self._run_ssh_command(f'cat > {self.DEFAULT_FILEPATH}',
                                        stdin=f'{self.tag}\n{info}\n')  # NOTE: pass the content via stdin so the remote shell does not interpret it
            return True
        except RuntimeError:
            print('Could not write mutex file')
            return False

    @property
    def tag(self) -> str:
        return f'{self.user_id} {datetime.now().isoformat()}'

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

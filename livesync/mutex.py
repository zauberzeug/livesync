import logging
import socket
import subprocess
from datetime import datetime, timedelta
from typing import Optional


class Mutex:
    DEFAULT_FILEPATH = '~/.livesync_mutex'

    def __init__(self, host: str, port: int) -> None:
        self.host = host
        self.port = port
        self.occupant: Optional[str] = None
        self.user_id = socket.gethostname()

    def is_free(self) -> bool:
        try:
            command = f'[ -f {self.DEFAULT_FILEPATH} ] && cat {self.DEFAULT_FILEPATH} || echo'
            output = self._run_ssh_command(command).strip()
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

    def set(self, info: str) -> bool:
        if not self.is_free():
            return False
        try:
            self._run_ssh_command(f'echo "{self.tag}\n{info}" > {self.DEFAULT_FILEPATH}')
            return True
        except subprocess.CalledProcessError:
            print('Could not write mutex file')
            return False

    @property
    def tag(self) -> str:
        return f'{self.user_id} {datetime.now().isoformat()}'

    def _run_ssh_command(self, command: str) -> str:
        ssh_command = ['ssh', self.host, '-p', str(self.port), command]
        return subprocess.check_output(ssh_command, stderr=subprocess.DEVNULL).decode()

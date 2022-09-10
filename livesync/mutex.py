import logging
import socket
import subprocess
from datetime import datetime, timedelta

MUTEX_FILEPATH = '~/.livesync_mutex'


class Mutex:

    def __init__(self, host: str) -> None:
        self.host = host
        self.occupant: str = None
        self.user_id = socket.gethostname()

    def is_free(self, info: str) -> bool:
        try:
            command = ['ssh', self.host, f'cat {MUTEX_FILEPATH} || echo "{self.tag}\n{info}"']
            output = subprocess.check_output(command, stderr=subprocess.DEVNULL).decode().splitlines()[0]
            words = output.strip().split()
            self.occupant = words[0]
            occupant_ok = self.occupant == self.user_id
            mutex_datetime = datetime.fromisoformat(words[1])
            mutex_expired = datetime.now() - mutex_datetime > timedelta(seconds=15)
            return occupant_ok or mutex_expired
        except:
            logging.exception('Could not access target system')
            return False

    def set(self, info: str) -> bool:
        if not self.is_free(info):
            return False
        try:
            command = ['ssh', self.host, f'echo "{self.tag}\n{info}" > {MUTEX_FILEPATH}']
            subprocess.check_output(command, stderr=subprocess.DEVNULL)
            return True
        except subprocess.CalledProcessError:
            print('Could not write mutex file')
            return False

    @property
    def tag(self) -> str:
        return f'{self.user_id} {datetime.now().isoformat()}'

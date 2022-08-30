import logging
import socket
import subprocess
import time


class Mutex:

    def __init__(self, host: str) -> None:
        self.host = host
        self.occupant: str = None
        self.user_id = socket.gethostname()

    def is_free(self) -> bool:
        try:
            output = subprocess.check_output(
                ['ssh', self.host, f'cat ~/.livesync_mutex || echo "{self.tag}"'],
                stderr=subprocess.DEVNULL).decode()
            words = output.strip().split()
            self.occupant = words[0]
            occupant_ok = self.occupant == self.user_id
            time_elapsed = time.time() - float(words[1]) > 15
            return occupant_ok or time_elapsed
        except:
            logging.exception('Could not read mutex file')
            return False

    def set(self) -> bool:
        if not self.is_free():
            return False
        try:
            subprocess.check_output(
                ['ssh', self.host, f'echo "{self.tag}" > ~/.livesync_mutex'],
                stderr=subprocess.DEVNULL
            )
            return True
        except subprocess.CalledProcessError:
            print('Could not write mutex file')
            return False

    def remove(self) -> None:
        try:
            subprocess.check_output(['ssh', self.host, f'rm ~/.livesync_mutex'], stderr=subprocess.DEVNULL)
            return True
        except subprocess.CalledProcessError:
            print('Could not remove mutex file')
            return False

    @property
    def tag(self) -> str:
        return f'{self.user_id} {time.time():.3f}'

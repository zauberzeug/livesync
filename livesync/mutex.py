import logging
import subprocess
import time


class Mutex:

    def __init__(self, host: str) -> None:
        self.host = host
        self.occupant: str = None

    def is_free(self, user_id: str) -> bool:
        try:
            output = subprocess.check_output(
                ['ssh', self.host, 'cat ~/.sync_mutex'],
                stderr=subprocess.DEVNULL).decode()
        except subprocess.CalledProcessError:
            return True
        try:
            words = output.strip().split()
            self.occupant = words[0]
            occupant_ok = self.occupant == user_id
            time_elapsed = time.time() - float(words[1]) > 15
            return occupant_ok or time_elapsed
        except:
            logging.exception('Could not read mutex file')
            return False

    def set(self, user_id: str) -> bool:
        if not self.is_free(user_id):
            return False
        try:
            subprocess.check_output(
                ['ssh', self.host, f'echo "{user_id} {time.time():.3f}" > ~/.sync_mutex'],
                stderr=subprocess.DEVNULL
            )
            return True
        except subprocess.CalledProcessError:
            print('Could not write mutex file')
            return False

    def remove(self) -> None:
        try:
            subprocess.check_output(['ssh', self.host, f'rm ~/.sync_mutex'], stderr=subprocess.DEVNULL)
            return True
        except subprocess.CalledProcessError:
            print('Could not remove mutex file')
            return False

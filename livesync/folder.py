import os
from typing import List


class Folder:

    def __init__(self, local_dir: str, target_host: str) -> None:
        self.local_dir = os.path.abspath(local_dir)
        self.target_host = target_host

    @property
    def ssh_target(self) -> str:
        return f'{self.target_host}:{os.path.basename(os.path.realpath(self.local_dir))}'

    @property
    def is_valid(self) -> bool:
        return os.path.isdir(self.local_dir)

    def get_excludes(self) -> List[str]:
        return ['.git/', '__pycache__/', '.DS_Store'] + \
            self._parse_ignore_file(f'{self.local_dir}/.syncignore') + \
            self._parse_ignore_file(f'{self.local_dir}/.gitignore')

    @staticmethod
    def _parse_ignore_file(path: str) -> List[str]:
        if not os.path.isfile(path):
            return []
        with open(path) as f:
            return [line.strip() for line in f.readlines() if not line.startswith('#')]

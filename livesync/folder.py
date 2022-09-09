import asyncio
import os
import subprocess
from typing import List

import watchfiles


class Folder:

    def __init__(self, local_dir: str, target_host: str) -> None:
        self.local_dir = os.path.abspath(local_dir)
        self.target_host = target_host

        self._stop_watching = asyncio.Event()

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

    def get_summary(self) -> str:
        summary = f'{self.local_dir} --> {self.ssh_target}\n'
        try:
            cmd = ['git', 'log', '--pretty=format:[%h]\n', '-n', '1']
            summary += subprocess.check_output(cmd, cwd=self.local_dir).decode()
            cmd = ['git', 'status', '--short', '--branch']
            summary += subprocess.check_output(cmd, cwd=self.local_dir).decode()
        except:
            pass  # maybe no git installed
        return summary

    async def watch(self) -> None:
        async for changes in watchfiles.awatch(self.local_dir, stop_event=self._stop_watching):
            for change, filepath in changes:
                print('?+U-'[change], filepath)
            self.sync()

    def stop_watching(self) -> None:
        self._stop_watching.set()

    def sync(self) -> subprocess.Popen:
        args = '--prune-empty-dirs --delete -avz --itemize-changes'
        args += ''.join(f' --exclude="{e}"' for e in self.get_excludes())
        command = f'rsync {args} {self.local_dir}/ {self.ssh_target}'
        return subprocess.Popen(
            command, shell=True, preexec_fn=os.setsid, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)

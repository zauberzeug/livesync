import asyncio
import os
import subprocess
from typing import List, Optional

import pathspec
import watchfiles


class Folder:

    def __init__(self, local_dir: str, target_host: str) -> None:
        self.local_dir = os.path.abspath(local_dir)
        self.target_host = target_host

        # https://stackoverflow.com/a/22090594/3419103
        self._ignore_spec = pathspec.PathSpec.from_lines(pathspec.patterns.GitWildMatchPattern, self.get_excludes())

        self._stop_watching = asyncio.Event()

    @property
    def target_path(self) -> str:
        return os.path.basename(os.path.realpath(self.local_dir))

    @property
    def ssh_target(self) -> str:
        return f'{self.target_host}:{self.target_path}'

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
        if not os.path.exists(os.path.join(self.local_dir, '.git')):
            return summary
        try:
            cmd = ['git', 'log', '--pretty=format:[%h]\n', '-n', '1']
            summary += subprocess.check_output(cmd, cwd=self.local_dir).decode()
            cmd = ['git', 'status', '--short', '--branch']
            summary += subprocess.check_output(cmd, cwd=self.local_dir).decode().strip()
        except:
            pass  # maybe git is not installed
        return summary

    async def watch(self, on_change_command: Optional[str]) -> None:
        try:
            async for changes in watchfiles.awatch(self.local_dir, stop_event=self._stop_watching,
                                                   watch_filter=lambda _, filepath: not self._ignore_spec.match_file(filepath)):
                for change, filepath in changes:
                    print('?+U-'[change], filepath)
                self.sync(on_change_command)
        except RuntimeError as e:
            if 'Already borrowed' not in str(e):
                raise

    def stop_watching(self) -> None:
        self._stop_watching.set()

    def sync(self, post_sync_command: Optional[str] = None) -> None:
        args = '--prune-empty-dirs --delete -avz --checksum --no-t'
        args += ''.join(f' --exclude="{e}"' for e in self.get_excludes())
        command = f'rsync {args} {self.local_dir}/ {self.ssh_target}'
        if post_sync_command:
            command += f'; ssh {self.target_host} "cd {self.target_path}; {post_sync_command}"'
        subprocess.run(command, shell=True, stdout=subprocess.DEVNULL)

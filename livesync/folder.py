
import asyncio
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

import pathspec
import watchfiles

KWONLY_SLOTS = {'kw_only': True, 'slots': True} if sys.version_info >= (3, 10) else {}


@dataclass(**KWONLY_SLOTS)
class Target:
    host: str
    port: int
    root: Path


class Folder:

    def __init__(self, local_dir: Path, target: Target) -> None:
        self.local_path = local_dir.resolve()  # one should avoid `absolute` if Python < 3.11
        self.target = target

        # from https://stackoverflow.com/a/22090594/3419103
        self._ignore_spec = pathspec.PathSpec.from_lines(
            pathspec.patterns.gitwildmatch.GitWildMatchPattern, self.get_excludes())

        self._stop_watching = asyncio.Event()

    @property
    def target_folder(self) -> Path:
        return Path(self.local_path.stem)

    @property
    def target_path(self) -> Path:
        return self.target.root / self.target_folder

    @property
    def ssh_path(self) -> str:
        return f'{self.target.host}:{self.target_path}'

    def get_excludes(self) -> List[str]:
        return ['.git/', '__pycache__/', '.DS_Store', '*.tmp', '.env'] + \
            self._parse_ignore_file(self.local_path/'.syncignore') + \
            self._parse_ignore_file(self.local_path/'.gitignore')

    @staticmethod
    def _parse_ignore_file(path: Path) -> List[str]:
        if not path.is_file():
            return []
        with path.open() as f:
            return [line.strip() for line in f.readlines() if not line.startswith('#')]

    def get_summary(self) -> str:
        summary = f'{self.local_path} --> {self.ssh_path}\n'
        if not (self.local_path / '.git').exists():
            return summary
        try:
            cmd = ['git', 'log', '--pretty=format:[%h]\n', '-n', '1']
            summary += subprocess.check_output(cmd, cwd=self.local_path).decode()
            cmd = ['git', 'status', '--short', '--branch']
            summary += subprocess.check_output(cmd, cwd=self.local_path).decode().strip() + '\n'
        except:
            pass  # maybe git is not installed
        return summary

    async def watch(self, on_change_command: Optional[str]) -> None:
        try:
            async for changes in watchfiles.awatch(self.local_path, stop_event=self._stop_watching,
                                                   watch_filter=lambda _, filepath: not self._ignore_spec.match_file(filepath)):
                for change, filepath in changes:
                    print('?+U-'[change], filepath)
                self.sync(on_change_command)
        except RuntimeError as e:
            if 'Already borrowed' not in str(e):
                raise

    def stop_watching(self) -> None:
        self._stop_watching.set()

    def make_target_dirs(self) -> None:
        print(f'make target dirs {self.target_path}')
        port_arg = f'-p {self.target.port}' if self.target.port != 22 else ''
        command = f'ssh {self.target.host} {port_arg} "mkdir -p {self.target_path}"'
        result = subprocess.run(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        print(result.stdout.decode())

    def sync(self, post_sync_command: Optional[str] = None) -> None:
        args = '--prune-empty-dirs --delete -avz --checksum --no-t'
        # args += ' --mkdirs'  # INFO: this option is not available in rsync < 3.2.3
        args += ''.join(f' --exclude="{e}"' for e in self.get_excludes())
        if self.target.port != 22:
            args += f' -e "ssh -p {self.target.port}"'

        command = f'rsync {args} {self.local_path}/ {self.ssh_path}/'
        subprocess.run(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        if post_sync_command:
            port_arg = f'-p {self.target.port}' if self.target.port != 22 else ''
            command = f'ssh {self.target.host} {port_arg} "cd {self.target_path}; {post_sync_command}"'
            result = subprocess.run(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            print(result.stdout.decode())

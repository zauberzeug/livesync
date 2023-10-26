import asyncio
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

import pathspec
import watchfiles

KWONLY_SLOTS = {'kw_only': True, 'slots': True} if sys.version_info >= (3, 10) else {}
DEFAULT_IGNORES = ['.git/', '__pycache__/', '.DS_Store', '*.tmp', '.env']


def run_subprocess(command: str, *, quiet: bool = False) -> None:
    result = subprocess.run(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=True)
    if not quiet:
        print(result.stdout.decode())


@dataclass(**KWONLY_SLOTS)
class Target:
    host: str
    port: int
    root: Path

    def make_target_root_directory(self) -> None:
        print(f'make target root directory {self.root}')
        run_subprocess(f'ssh {self.host} -p {self.port} "mkdir -p {self.root}"')


class Folder:

    def __init__(self, local_dir: Path, target: Target) -> None:
        self.local_path = local_dir.resolve()  # one should avoid `absolute` if Python < 3.11
        self.target = target

        # from https://stackoverflow.com/a/22090594/3419103
        match_pattern = pathspec.patterns.gitwildmatch.GitWildMatchPattern
        self._ignore_spec = pathspec.PathSpec.from_lines(match_pattern, self.get_ignores())

        self._stop_watching = asyncio.Event()

    @property
    def target_path(self) -> Path:
        return self.target.root / self.local_path.stem

    @property
    def ssh_path(self) -> str:
        return f'{self.target.host}:{self.target_path}'

    def get_ignores(self) -> List[str]:
        path = self.local_path / '.syncignore'
        if not path.is_file():
            path.write_text('\n'.join(DEFAULT_IGNORES))
        return [line.strip() for line in path.read_text().splitlines() if not line.startswith('#')]

    def get_summary(self) -> str:
        summary = f'{self.local_path} --> {self.ssh_path}\n'
        if not (self.local_path / '.git').exists():
            return summary
        try:
            cmd = ['git', 'log', '--pretty=format:[%h]\n', '-n', '1']
            summary += subprocess.check_output(cmd, cwd=self.local_path).decode()
            cmd = ['git', 'status', '--short', '--branch']
            summary += subprocess.check_output(cmd, cwd=self.local_path).decode().strip() + '\n'
        except Exception:
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

    def sync(self, post_sync_command: Optional[str] = None) -> None:
        args = '--prune-empty-dirs --delete -avz --checksum --no-t'
        # args += ' --mkdirs'  # INFO: this option is not available in rsync < 3.2.3
        args += ''.join(f' --exclude="{e}"' for e in self.get_ignores())
        args += f' -e "ssh -p {self.target.port}"'
        run_subprocess(f'rsync {args} {self.local_path}/ {self.ssh_path}/', quiet=True)
        if post_sync_command:
            run_subprocess(f'ssh {self.target.host} -p {self.target.port} "cd {self.target_path}; {post_sync_command}"')

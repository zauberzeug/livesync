from __future__ import annotations

import asyncio
import subprocess
import sys
from pathlib import Path
from typing import Callable, List, Optional, Set, Union

import pathspec
import watchfiles


def run_subprocess(command: str, *, quiet: bool = False) -> None:
    try:
        result = subprocess.run(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=True)
        if not quiet:
            print(result.stdout.decode())
    except subprocess.CalledProcessError as e:
        print(e.stdout.decode())
        raise


class Folder:
    DEFAULT_IGNORES = ['.git/', '__pycache__/', '.DS_Store', '*.tmp', '.env']
    DEFAULT_RSYNC_ARGS = ['--prune-empty-dirs', '--delete', '-a', '-v', '-z', '--checksum', '--no-t']

    def __init__(self,
                 source_path: Union[str, Path],
                 target: str, *,
                 ssh_port: int = 22,
                 on_change: Optional[Union[str, Callable]] = None,
                 mutex_interval: float = 10,
                 ) -> None:
        self.source_path = Path(source_path).resolve()  # one should avoid `absolute` if Python < 3.11
        self.target = target
        self.host, self.target_path = target.split(':')
        self.ssh_port = ssh_port
        self.on_change = on_change or None
        self.mutex_interval = mutex_interval
        self._rsync_args: Set[str] = set(self.DEFAULT_RSYNC_ARGS)

        if not self.source_path.is_dir():
            print(f'Invalid path: {self.source_path}')
            sys.exit(1)

        run_subprocess(f'ssh {self.host} -p {self.ssh_port} "mkdir -p {self.target_path}"')

        # from https://stackoverflow.com/a/22090594/3419103
        match_pattern = pathspec.patterns.gitwildmatch.GitWildMatchPattern
        self._ignore_spec = pathspec.PathSpec.from_lines(match_pattern, self._get_ignores())

        self._stop_watching = asyncio.Event()

    def rsync_args(self,
                   add: Optional[str] = None,
                   remove: Optional[str] = None,
                   replace: Optional[str] = None) -> Folder:
        if replace is not None:
            self._rsync_args.clear()
            self._rsync_args.update(replace.split())
        if add is not None:
            self._rsync_args.update(add.split())
        if remove is not None:
            self._rsync_args.difference_update(remove.split())
        return self

    def _get_ignores(self) -> List[str]:
        path = self.source_path / '.syncignore'
        if not path.is_file():
            path.write_text('\n'.join(self.DEFAULT_IGNORES))
        return [line.strip() for line in path.read_text().splitlines() if not line.startswith('#')]

    def get_summary(self) -> str:
        summary = f'{self.source_path} --> {self.target}\n'
        if not (self.source_path / '.git').exists():
            return summary
        try:
            cmd = ['git', 'log', '--pretty=format:[%h]\n', '-n', '1']
            summary += subprocess.check_output(cmd, cwd=self.source_path).decode()
            cmd = ['git', 'status', '--short', '--branch']
            summary += subprocess.check_output(cmd, cwd=self.source_path).decode().strip() + '\n'
        except Exception:
            pass  # maybe git is not installed
        return summary

    async def watch(self) -> None:
        try:
            async for changes in watchfiles.awatch(self.source_path, stop_event=self._stop_watching,
                                                   watch_filter=lambda _, filepath: not self._ignore_spec.match_file(filepath)):
                for change, filepath in changes:
                    print('?+U-'[change], filepath)
                self.sync()
        except RuntimeError as e:
            if 'Already borrowed' not in str(e):
                raise

    def stop_watching(self) -> None:
        self._stop_watching.set()

    def sync(self) -> None:
        args = ' '.join(self._rsync_args)
        args += ''.join(f' --exclude="{e}"' for e in self._get_ignores())
        args += f' -e "ssh -p {self.ssh_port}"'
        run_subprocess(f'rsync {args} {self.source_path}/ {self.target}/', quiet=True)
        if isinstance(self.on_change, str):
            run_subprocess(f'ssh {self.host} -p {self.ssh_port} "cd {self.target_path}; {self.on_change}"')
        if callable(self.on_change):
            self.on_change()

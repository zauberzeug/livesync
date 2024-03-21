from __future__ import annotations

import asyncio
import subprocess
import sys
from pathlib import Path
from typing import Callable, List, Optional, Union

import pathspec
import watchfiles

from .run_subprocess import run_subprocess


class Folder:
    DEFAULT_IGNORES = ['.git/', '__pycache__/', '.DS_Store', '*.tmp', '.env']
    DEFAULT_RSYNC_ARGS = ['--prune-empty-dirs', '--delete', '-a', '-v', '-z', '--checksum', '--no-t']

    def __init__(self,
                 source_path: Union[str, Path],
                 target: str, *,
                 ssh_port: int = 22,
                 on_change: Optional[Union[str, Callable]] = None,
                 ) -> None:
        self.source_path = Path(source_path).resolve()  # one should avoid `absolute` if Python < 3.11
        if ':' not in target:
            target = f'{target}:{self.source_path.name}'
        self.target = target
        self.host, self.target_path = target.split(':')
        self.ssh_port = ssh_port
        self.on_change = on_change or None
        self._rsync_args: List[str] = self.DEFAULT_RSYNC_ARGS[:]
        self._stop_watching = asyncio.Event()

        if not self.source_path.is_dir():
            print(f'Invalid path: {self.source_path}')
            sys.exit(1)

        match_pattern = pathspec.patterns.gitwildmatch.GitWildMatchPattern  # https://stackoverflow.com/a/22090594/3419103
        self._ignore_spec = pathspec.PathSpec.from_lines(match_pattern, self._get_ignores())

    def rsync_args(self,
                   add: Optional[str] = None,
                   remove: Optional[str] = None,
                   replace: Optional[str] = None) -> Folder:
        if replace is not None:
            self._rsync_args.clear()
        add_args = (add or '').split() + (replace or '').split()
        remove_args = remove.split() if remove else []
        self._rsync_args += [arg for arg in add_args if arg not in self._rsync_args]
        self._rsync_args = [arg for arg in self._rsync_args if arg not in remove_args]
        return self

    def _get_ignores(self) -> List[str]:
        path = self.source_path / '.syncignore'
        if not path.is_file():
            path.write_text('\n'.join(self.DEFAULT_IGNORES))
        ignores = [line.strip() for line in path.read_text().splitlines() if not line.startswith('#')]
        ignores += [ignore.rstrip('/\\') for ignore in ignores if ignore.endswith('/') or ignore.endswith('\\')]
        return ignores

    def get_summary(self) -> str:
        summary = f'{self.source_path} --> {self.target}\n'
        try:
            cmd = ['git', 'rev-parse', '--is-inside-work-tree']
            subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        except subprocess.CalledProcessError:
            pass  # not a git repo, git is not installed, or something else
        else:
            cmd = ['git', 'log', '--pretty=format:[%h]\n', '-n', '1']
            summary += subprocess.check_output(cmd, cwd=self.source_path).decode()
            cmd = ['git', 'status', '--short', '--branch']
            summary += subprocess.check_output(cmd, cwd=self.source_path).decode().strip() + '\n'
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

    def sync(self) -> None:
        args = ' '.join(self._rsync_args)
        args += ''.join(f' --exclude="{e}"' for e in self._get_ignores())
        args += f' -e "ssh -p {self.ssh_port}"'  # NOTE: use SSH with custom port
        args += f' --rsync-path="mkdir -p {self.target_path} && rsync"'  # NOTE: create target folder if not exists
        run_subprocess(f'rsync {args} "{self.source_path}/" "{self.target}/"', quiet=True)
        if isinstance(self.on_change, str):
            run_subprocess(f'ssh {self.host} -p {self.ssh_port} "cd {self.target_path}; {self.on_change}"')
        if callable(self.on_change):
            self.on_change()

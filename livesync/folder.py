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
    """Represents a folder to be synchronized with a remote target via rsync over SSH."""
    DEFAULT_IGNORES = ['.git/', '.jj/', '__pycache__/', '.DS_Store', '*.tmp', '.env', '.venv']
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
        """Add, remove, or replace rsync arguments for this folder."""
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
        """Return a summary of the folder's source and target paths, along with git revision information if applicable."""
        summary = f'{self.source_path} --> {self.target}\n'
        try:
            cmd = ['git', 'rev-parse', '--is-inside-work-tree']
            subprocess.run(cmd, check=True, cwd=self.source_path, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        except (subprocess.CalledProcessError, FileNotFoundError):
            pass  # not a git repo or git is not installed
        else:
            if version := self._build_version():
                summary += f'[{version}]\n'
            cmd = ['git', 'status', '--short', '--branch']
            summary += subprocess.check_output(cmd, cwd=self.source_path).decode().strip() + '\n'
        return summary

    def _build_version(self) -> str:
        """Build a dunamai-style version string from git, e.g. `0.1.0.post43.dev0+3f6ee0e`.

        The nearest tag is the base version, the number of commits since then is `.post<distance>.dev0`,
        and the short commit hash is appended as `+<hash>` (always, so the exact revision is included
        even when sitting right on a tag: `<base>.post0.dev0+<hash>`). With no tag the base is `0.0.0`
        and the distance is the total number of commits. Returns '' if the repo has no commit yet.
        No dunamai dependency; uncommon cases (custom tag patterns, pre-releases, epochs, dirty
        markers) are not replicated.
        """
        try:
            cmd = ['git', 'rev-parse', '--short', 'HEAD']
            commit = subprocess.check_output(cmd, cwd=self.source_path, stderr=subprocess.PIPE).decode().strip()
        except subprocess.CalledProcessError:
            return ''  # no commit yet
        try:
            cmd = ['git', 'describe', '--tags', '--abbrev=0']
            tag = subprocess.check_output(cmd, cwd=self.source_path, stderr=subprocess.PIPE).decode().strip()
            base = tag.removeprefix('v') if tag[1:2].isdigit() else tag
            cmd = ['git', 'rev-list', f'refs/tags/{tag}..HEAD', '--count']
        except subprocess.CalledProcessError:
            base = '0.0.0'  # no tags -> 0.0.0 with the total commit count as distance
            cmd = ['git', 'rev-list', 'HEAD', '--count']
        try:
            distance = subprocess.check_output(cmd, cwd=self.source_path, stderr=subprocess.PIPE).decode().strip()
        except subprocess.CalledProcessError:
            return ''  # e.g. a shallow clone where the found tag is not reachable
        return f'{base}.post{distance}.dev0+{commit}'

    async def watch(self) -> None:
        """Watch the source folder for changes and synchronize to the target when changes occur."""
        try:
            async for changes in watchfiles.awatch(self.source_path, stop_event=self._stop_watching,
                                                   watch_filter=lambda _, filepath: not self._ignore_spec.match_file(filepath)):
                for change, filepath in changes:
                    print('?+U-'[change], filepath)
                await self.sync()
        except RuntimeError as e:
            if 'Already borrowed' not in str(e):
                raise

    async def sync(self) -> None:
        """Synchronize the source folder to the target using rsync over SSH, and run the on_change command if specified."""
        args = ' '.join(self._rsync_args)
        args += ''.join(f' --exclude="{e}"' for e in self._get_ignores())
        args += f' -e "ssh -p {self.ssh_port}"'  # NOTE: use SSH with custom port
        args += f' --rsync-path="mkdir -p {self.target_path} && rsync"'  # NOTE: create target folder if not exists
        await run_subprocess(f'rsync {args} "{self.source_path}/" "{self.target}/"', quiet=True)
        if isinstance(self.on_change, str):
            await run_subprocess(f'ssh {self.host} -p {self.ssh_port} "cd {self.target_path}; {self.on_change}"')
        if callable(self.on_change):
            self.on_change()

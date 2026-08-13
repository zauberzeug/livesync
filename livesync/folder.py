from __future__ import annotations

import asyncio
import shlex
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
        self._ignores = self._get_ignores()
        self._ignore_spec = pathspec.PathSpec.from_lines(match_pattern, self._ignores)

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
        ignores: List[str] = []
        for line in path.read_text().splitlines():
            pattern = line.strip()
            if pattern and not pattern.startswith('#') and pattern != '!':
                ignores.append(pattern)
        return ignores

    @staticmethod
    def _is_directory_pattern(pattern: str) -> bool:
        return pattern.endswith('/') or pattern.endswith('\\')

    @staticmethod
    def _is_anchored(pattern: str) -> bool:
        """Tell whether gitignore anchors this pattern to the source folder.

        A slash at the start or in the middle anchors the pattern, while a slashless one like
        ``node_modules/`` matches at any depth. rsync patterns anchor only on a leading slash,
        so the middle-slash case needs one adding.
        """
        return '/' in pattern.rstrip('/\\')

    @classmethod
    def _anchor(cls, pattern: str) -> str:
        return pattern if pattern.startswith('/') or not cls._is_anchored(pattern) else f'/{pattern}'

    @staticmethod
    def _without_trailing_slash(pattern: str) -> str:
        return pattern.rstrip('/\\')

    @classmethod
    def _normalise_for_descendant_check(cls, pattern: str) -> str:
        return cls._without_trailing_slash(pattern.lstrip('!').lstrip('/'))

    @classmethod
    def _directory_pattern_has_negation(cls, pattern: str, negations: List[str]) -> bool:
        directory = cls._normalise_for_descendant_check(pattern)
        if not directory or not negations:
            return False
        if any(char in directory for char in '*?['):
            return True  # a glob may cover a negated path, so keep the directory traversable
        for negation in negations:
            candidate = cls._normalise_for_descendant_check(negation)
            if candidate == directory or candidate.startswith(f'{directory}/'):
                return True
            if not cls._is_anchored(pattern) and f'/{directory}/' in candidate:
                return True  # a slashless pattern matches at any depth, so a nested negation counts
        return False

    @staticmethod
    def _ancestor_directory_patterns(pattern: str) -> List[str]:
        parts = [part for part in pattern.strip('/\\').split('/')[:-1] if part]
        return ['/' + '/'.join(parts[:index]) + '/' for index in range(1, len(parts) + 1)]

    @classmethod
    def _rsync_rules_for_negation(cls, pattern: str) -> List[str]:
        rule = cls._anchor(pattern[1:])
        rules = [f'+ {ancestor}' for ancestor in cls._ancestor_directory_patterns(rule)]
        if cls._is_directory_pattern(rule):
            rules.append(f'+ {rule}')
            rules.append(f'+ {rule}**')
        else:
            rules.append(f'+ {rule}')
        return rules

    def _get_rsync_filter_rules(self) -> List[str]:
        negations = [pattern for pattern in self._ignores if pattern.startswith('!')]
        rules: List[str] = []
        for pattern in reversed(self._ignores):
            if pattern.startswith('!'):
                rules.extend(self._rsync_rules_for_negation(pattern))
            elif self._directory_pattern_has_negation(pattern, negations):
                # Ancestor '+' rules reopen this directory for traversal, so pruning it is not
                # an option: exclude its contents at any depth instead.
                anchored = self._anchor(pattern)
                rules.append(f'- {self._without_trailing_slash(anchored)}/**')
                if not self._is_directory_pattern(pattern):
                    rules.append(f'- {anchored}')
            else:
                rules.append(f'- {self._anchor(pattern)}')

        deduplicated: List[str] = []
        for rule in rules:
            if rule not in deduplicated:
                deduplicated.append(rule)
        return deduplicated

    def _get_rsync_filters(self) -> str:
        """Convert .syncignore patterns to rsync filter rules, supporting negation (!) prefixes.

        Rules are emitted in reverse .syncignore order so rsync's first-match-wins behavior
        matches pathspec's last-match-wins behavior.
        """
        return ''.join(f' --filter={shlex.quote(rule)}' for rule in self._get_rsync_filter_rules())

    def _is_ignored(self, filepath: str) -> bool:
        path = Path(filepath)
        try:
            path = path.resolve().relative_to(self.source_path)
        except ValueError:
            pass
        return self._ignore_spec.match_file(str(path))

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
                                                   watch_filter=lambda _, filepath: not self._is_ignored(filepath)):
                for change, filepath in changes:
                    print('?+U-'[change], filepath)
                await self.sync()
        except RuntimeError as e:
            if 'Already borrowed' not in str(e):
                raise

    async def sync(self) -> None:
        """Synchronize the source folder to the target using rsync over SSH, and run the on_change command if specified."""
        args = ' '.join(self._rsync_args)
        args += self._get_rsync_filters()
        args += f' -e "ssh -p {self.ssh_port}"'  # NOTE: use SSH with custom port
        args += f' --rsync-path="mkdir -p {self.target_path} && rsync"'  # NOTE: create target folder if not exists
        await run_subprocess(f'rsync {args} "{self.source_path}/" "{self.target}/"', quiet=True)
        if isinstance(self.on_change, str):
            await run_subprocess(f'ssh {self.host} -p {self.ssh_port} "cd {self.target_path}; {self.on_change}"')
        if callable(self.on_change):
            self.on_change()

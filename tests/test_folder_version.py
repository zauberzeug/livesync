"""Unit tests for the automatic version string in the mutex (see ``Folder.get_summary``).

Run with: ``uv run pytest tests/test_folder_version.py`` (or ``python -m pytest``).
"""
import os
import subprocess
from pathlib import Path

import pytest

from livesync import Folder

CLEAN_ENV = {
    'GIT_CONFIG_GLOBAL': '/dev/null',  # ignore the developer's global git config
    'GIT_CONFIG_SYSTEM': '/dev/null',
    'PATH': os.environ.get('PATH', ''),
}


def git(repo: Path, *args: str) -> str:
    env = {**CLEAN_ENV, 'HOME': str(repo)}
    return subprocess.check_output(['git', *args], cwd=repo, env=env, stderr=subprocess.PIPE).decode().strip()


def commit(repo: Path, message: str) -> None:
    (repo / 'file.txt').write_text(message)
    git(repo, 'add', '.')
    git(repo, 'commit', '-m', message)


def bracket(summary: str) -> str:
    """Return the content of the `[...]` revision line of the (single) folder block."""
    line = next(line for line in summary.splitlines() if line.startswith('['))
    return line[1:-1]


@pytest.fixture()
def repo(tmp_path: Path) -> Path:
    path = tmp_path / 'my_project'
    path.mkdir()
    git(path, 'init', '-b', 'main')
    git(path, 'config', 'user.email', 'test@example.com')
    git(path, 'config', 'user.name', 'Test')
    git(path, 'config', 'commit.gpgsign', 'false')
    return path


def test_no_tag_uses_zero_base_with_hash(repo: Path) -> None:
    """Without any tag the base is 0.0.0 and the distance is the total commit count, hash included."""
    commit(repo, 'initial')
    commit(repo, 'second')
    short = git(repo, 'rev-parse', '--short', 'HEAD')
    assert bracket(Folder(str(repo), 'target:~/p').get_summary()) == f'0.0.0.post2.dev0+{short}'


def test_repo_without_commits_omits_bracket(repo: Path) -> None:
    """A freshly initialised repo has no commit to describe, so no revision bracket is written."""
    summary = Folder(str(repo), 'target:~/p').get_summary()
    assert '[' not in summary


def test_exact_tag_uses_post0_dev0_with_hash(repo: Path) -> None:
    """On the tagged commit distance is 0, so the hash is still included via `.post0.dev0+<hash>`."""
    commit(repo, 'initial')
    git(repo, 'tag', 'v0.1.0')
    short = git(repo, 'rev-parse', '--short', 'HEAD')
    assert bracket(Folder(str(repo), 'target:~/p').get_summary()) == f'0.1.0.post0.dev0+{short}'


def test_tag_without_v_prefix_is_used_as_is(repo: Path) -> None:
    commit(repo, 'initial')
    git(repo, 'tag', '2.0.0')
    short = git(repo, 'rev-parse', '--short', 'HEAD')
    assert bracket(Folder(str(repo), 'target:~/p').get_summary()) == f'2.0.0.post0.dev0+{short}'


def test_tag_starting_with_v_but_no_digit_is_kept(repo: Path) -> None:
    """Only a `v` directly followed by a digit is a version prefix; other tags are used verbatim."""
    commit(repo, 'initial')
    git(repo, 'tag', 'version-2024')
    short = git(repo, 'rev-parse', '--short', 'HEAD')
    assert bracket(Folder(str(repo), 'target:~/p').get_summary()) == f'version-2024.post0.dev0+{short}'


def test_branch_with_same_name_as_tag_does_not_confuse_distance(repo: Path) -> None:
    """The distance is counted from `refs/tags/<tag>`, even if a branch shares the tag's name."""
    commit(repo, 'initial')
    git(repo, 'tag', 'v0.1.0')
    commit(repo, 'second')
    git(repo, 'branch', 'v0.1.0')  # ambiguous refname pointing at HEAD, not at the tagged commit
    short = git(repo, 'rev-parse', '--short', 'HEAD')
    assert bracket(Folder(str(repo), 'target:~/p').get_summary()) == f'0.1.0.post1.dev0+{short}'


def test_distance_shows_post_dev_with_hash(repo: Path) -> None:
    """Commits past the tag yield a dunamai-style `base.post<n>.dev0+<hash>`; the hash is not duplicated."""
    commit(repo, 'initial')
    git(repo, 'tag', 'v0.1.0')
    commit(repo, 'second')
    commit(repo, 'third')
    short = git(repo, 'rev-parse', '--short', 'HEAD')
    assert bracket(Folder(str(repo), 'target:~/p').get_summary()) == f'0.1.0.post2.dev0+{short}'


def test_version_is_recomputed_each_call(repo: Path) -> None:
    """get_summary derives the version from git on every call, so it stays live during a sync."""
    commit(repo, 'initial')
    git(repo, 'tag', 'v0.1.0')
    commit(repo, 'second')
    folder = Folder(str(repo), 'target:~/p')
    assert bracket(folder.get_summary()).startswith('0.1.0.post1.dev0+')
    commit(repo, 'third')
    assert bracket(folder.get_summary()).startswith('0.1.0.post2.dev0+')


def test_version_found_when_cwd_is_not_a_repo(repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """All git checks run in the source folder, not the process CWD (which may not be a repo)."""
    commit(repo, 'initial')
    git(repo, 'tag', 'v0.1.0')
    monkeypatch.chdir(tmp_path)
    assert bracket(Folder(str(repo), 'target:~/p').get_summary()).startswith('0.1.0.post0.dev0+')


def test_non_repo_source_omits_git_block_even_if_cwd_is_a_repo(repo: Path, tmp_path: Path,
                                                               monkeypatch: pytest.MonkeyPatch) -> None:
    """A non-repo source folder gets no git block, even when livesync runs from inside a git repo."""
    plain = tmp_path / 'plain'
    plain.mkdir()
    monkeypatch.chdir(repo)
    summary = Folder(str(plain), 'target:~/p').get_summary()
    assert summary == f'{plain.resolve()} --> target:~/p\n'


def test_failing_rev_list_omits_bracket(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """If counting the distance fails (e.g. shallow clone), the version is skipped instead of crashing."""
    commit(repo, 'initial')
    git(repo, 'tag', 'v0.1.0')
    original = subprocess.check_output

    def flaky(cmd, **kwargs):
        if 'rev-list' in cmd:
            raise subprocess.CalledProcessError(128, cmd)
        return original(cmd, **kwargs)
    monkeypatch.setattr('livesync.folder.subprocess.check_output', flaky)
    summary = Folder(str(repo), 'target:~/p').get_summary()
    assert '[' not in summary
    assert '## main' in summary


def test_bracket_survives_double_quote_escaping(repo: Path) -> None:
    """sync.get_summary replaces `"` with `'`; the version has no `"` and passes through intact."""
    from livesync.sync import get_summary
    commit(repo, 'initial')
    git(repo, 'tag', 'v0.1.0')
    assert '[0.1.0.post0.dev0+' in get_summary([Folder(str(repo), 'target:~/p')])


def test_no_git_produces_no_bracket_line(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """If git is unavailable the git block is skipped entirely, exactly as before."""
    def no_git(*_args, **_kwargs):
        raise FileNotFoundError('git')  # what subprocess.run raises when the binary is missing
    monkeypatch.setattr('livesync.folder.subprocess.run', no_git)
    summary = Folder(str(repo), 'target:~/p').get_summary()
    assert '[' not in summary
    assert summary == f'{Path(str(repo)).resolve()} --> target:~/p\n'

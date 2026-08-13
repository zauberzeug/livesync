"""Unit tests for ``.syncignore`` handling, including ``!`` negation (see ``Folder._get_rsync_filters``).

The scenarios below drive real rsync against a local target and compare the result with pathspec,
which is the oracle the file watcher uses. Run with: ``uv run pytest tests/test_syncignore.py``.
"""
import subprocess
from pathlib import Path
from typing import List, Optional

import pytest

from livesync import Folder

# Each scenario is a ``.syncignore`` plus the files to create in the source folder.
# The invariant under test: rsync transfers exactly the files that the watcher's pathspec
# does *not* ignore. Any divergence means either a file is pushed but its later edits are
# never noticed, or the watcher triggers syncs that never deliver the file.
SCENARIOS = [
    ('motivating example', ['build/', '!build/lizard.bin', '!build/lizard.elf'],
     ['build/lizard.bin', 'build/lizard.elf', 'build/other.o', 'src.py']),
    ('anchored directory', ['/build/', '!/build/lizard.bin'],
     ['build/lizard.bin', 'build/other.o', 'nested/build/lizard.bin', 'src.py']),
    ('later exclude overrides negation', ['*.log', '!debug.log', 'debug.log'],
     ['debug.log', 'other.log', 'keep.txt']),
    ('later wildcard overrides negation', ['!keep.txt', '*.txt'],
     ['keep.txt', 'other.txt', 'a.py']),
    ('negation before exclude', ['!build/keep.txt', 'build/'],
     ['build/keep.txt', 'build/other.o', 'top.py']),
    ('negated directory', ['build/', '!build/keep/'],
     ['build/keep/a.bin', 'build/keep/deeper/b.bin', 'build/other.o']),
    ('negation two levels deep', ['build/', '!build/sub/deep.bin'],
     ['build/sub/deep.bin', 'build/sub/other.o', 'build/top.o']),
    ('negation three levels deep', ['a/', '!a/b/c/f.bin'],
     ['a/b/c/f.bin', 'a/b/c/g.o', 'a/b/h.o', 'a/i.o']),
    ('two negations at different depths', ['build/', '!build/x.bin', '!build/sub/y.bin'],
     ['build/x.bin', 'build/sub/y.bin', 'build/sub/z.o', 'build/w.o']),
    ('negated directory with a deeper exclude', ['build/', '!build/keep/', 'build/keep/skip.o'],
     ['build/keep/a.bin', 'build/keep/skip.o', 'build/other.o']),
    ('glob negation', ['build/', '!build/*.bin'],
     ['build/a.bin', 'build/b.bin', 'build/c.o', 'build/sub/d.bin']),
    ('wildcard directory pattern', ['*.egg-info/', '!pkg.egg-info/KEEP'],
     ['pkg.egg-info/KEEP', 'pkg.egg-info/other', 'main.py']),
    ('negation without a matching exclude', ['!keep.txt'], ['keep.txt', 'a.py']),
    ('nested directories are excluded at any depth', ['node_modules/'],
     ['node_modules/a.js', 'pkg/node_modules/b.js', 'app.js']),
    ('default ignores', Folder.DEFAULT_IGNORES,
     ['.git/config', '.jj/repo', '__pycache__/x.pyc', '.DS_Store', 'a.tmp', '.env',
      '.venv/bin/python', 'main.py']),
    ('negation inside a slashless default ignore', [*Folder.DEFAULT_IGNORES, '!.venv/marker'],
     ['.venv/marker', '.venv/bin/python', 'main.py']),
    ('comments, blank lines and a bare negation', ['', '  # indented comment', '!', 'build/'],
     ['build/a.o', 'keep.py']),
    ('a slash in the middle anchors the pattern', ['a/b/', '!x/a/b/keep'],
     ['a/b/drop', 'x/a/b/keep', 'x/a/b/other', 'top']),
    ('a slashless pattern still matches at any depth', ['build/', '!x/build/keep'],
     ['build/drop', 'x/build/keep', 'x/build/other', 'top']),
]


def create_folder(path: Path, patterns: List[str], files: Optional[List[str]] = None) -> Folder:
    """Create a source folder with a ``.syncignore`` and the given files."""
    path.mkdir(parents=True, exist_ok=True)
    for file in files or []:
        (path / file).parent.mkdir(parents=True, exist_ok=True)
        (path / file).write_text(f'content of {file}')
    (path / '.syncignore').write_text('\n'.join(patterns))
    return Folder(path, 'target:~/project')


def sync_locally(folder: Folder, target: Path) -> List[str]:
    """Run the folder's real rsync invocation against a local target and return what arrived."""
    target.mkdir(parents=True, exist_ok=True)
    args = ' '.join(folder._rsync_args) + folder._get_rsync_filters()  # pylint: disable=protected-access
    subprocess.run(f'rsync {args} "{folder.source_path}/" "{target}/"',
                   shell=True, check=True, capture_output=True, text=True)
    return sorted(str(path.relative_to(target)) for path in target.rglob('*') if path.is_file())


@pytest.mark.parametrize('patterns,files', [scenario[1:] for scenario in SCENARIOS],
                         ids=[scenario[0] for scenario in SCENARIOS])
def test_rsync_transfers_exactly_what_the_watcher_watches(tmp_path: Path,
                                                          patterns: List[str],
                                                          files: List[str]) -> None:
    """rsync must deliver exactly the files the watcher considers relevant, and nothing else."""
    folder = create_folder(tmp_path / 'source', patterns, files)

    transferred = sync_locally(folder, tmp_path / 'target')

    watched = sorted(file for file in [*files, '.syncignore']
                     if not folder._ignore_spec.match_file(file))  # pylint: disable=protected-access
    assert transferred == watched


def test_negated_files_are_synced_while_the_rest_of_the_directory_is_not(tmp_path: Path) -> None:
    """The motivating example: firmware artifacts arrive while the rest of the build directory does not."""
    folder = create_folder(tmp_path / 'source', ['/build/', '!/build/lizard.bin', '!/build/lizard.elf'],
                           ['build/lizard.bin', 'build/lizard.elf', 'build/other.o', 'main.py'])
    target = tmp_path / 'target'

    sync_locally(folder, target)

    assert (target / 'build' / 'lizard.bin').is_file()
    assert (target / 'build' / 'lizard.elf').is_file()
    assert not (target / 'build' / 'other.o').exists()
    assert (target / 'main.py').is_file()


def test_edits_to_negated_files_are_not_ignored_by_the_watcher(tmp_path: Path) -> None:
    """A negated file must be watched, otherwise its edits never trigger a sync."""
    source = tmp_path / 'source'
    folder = create_folder(source, ['build/', '!build/lizard.bin'], ['build/lizard.bin', 'build/other.o'])

    assert not folder._is_ignored(str(source / 'build' / 'lizard.bin'))  # pylint: disable=protected-access
    assert folder._is_ignored(str(source / 'build' / 'other.o'))  # pylint: disable=protected-access


def test_anchored_patterns_match_on_the_watcher_side(tmp_path: Path) -> None:
    """Anchored patterns must apply at the top level only, on the watcher side as well as for rsync."""
    source = tmp_path / 'source'
    folder = create_folder(source, ['/build/'], ['build/other.o', 'nested/build/keep.o'])

    assert folder._is_ignored(str(source / 'build' / 'other.o'))  # pylint: disable=protected-access
    assert not folder._is_ignored(str(source / 'nested' / 'build' / 'keep.o'))  # pylint: disable=protected-access


def test_comments_blank_lines_and_bare_negations_are_dropped(tmp_path: Path) -> None:
    """Indented comments, blank lines and a bare ``!`` are no-ops rather than patterns."""
    folder = create_folder(tmp_path / 'source', ['', '  # indented comment', '!', 'build/'])

    assert folder._get_ignores() == ['build/']  # pylint: disable=protected-access


def test_directories_without_negations_are_pruned(tmp_path: Path) -> None:
    """A directory containing no negation is pruned entirely, which lets rsync skip descending into it."""
    folder = create_folder(tmp_path / 'source', ['node_modules/'])

    assert folder._get_rsync_filter_rules() == ['- node_modules/']  # pylint: disable=protected-access


def test_negations_are_emitted_with_ancestor_includes_in_reverse_order(tmp_path: Path) -> None:
    """A deep negation needs ancestor includes, and rules follow reversed file order for first-match-wins."""
    folder = create_folder(tmp_path / 'source', ['build/', '!build/sub/deep.bin'])

    assert folder._get_rsync_filter_rules() == [  # pylint: disable=protected-access
        '+ /build/',  # anchored: the negation contains a slash, so gitignore roots it
        '+ /build/sub/',
        '+ /build/sub/deep.bin',
        '- build/**',  # unanchored: a slashless pattern matches at any depth
    ]


@pytest.mark.xfail(reason='rsync has no zero-directory form of "/**/", so a/**/b/ does not cover a/b/')
def test_interior_double_star_matches_zero_directories(tmp_path: Path) -> None:
    """Known limitation, pre-existing: gitignore's ``a/**/b/`` also matches ``a/b/``, rsync's does not."""
    folder = create_folder(tmp_path / 'source', ['a/**/b/'], ['a/b/drop', 'a/c/b/drop', 'top'])

    assert sync_locally(folder, tmp_path / 'target') == ['.syncignore', 'top']


def test_filter_rules_are_shell_quoted(tmp_path: Path) -> None:
    """Patterns are interpolated into a shell command, so every rule must be quoted."""
    folder = create_folder(tmp_path / 'source', ['$(touch pwned)'])

    assert folder._get_rsync_filters() == " --filter='- $(touch pwned)'"  # pylint: disable=protected-access

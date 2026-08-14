"""Translate ``.syncignore`` patterns into rsync filter rules, supporting negation (!) prefixes."""
from typing import List


def get_rsync_filter_rules(patterns: List[str]) -> List[str]:
    """Convert .syncignore patterns to rsync filter rules.

    Rules are emitted in reverse .syncignore order so rsync's first-match-wins behavior
    matches pathspec's last-match-wins behavior.
    """
    negations = [pattern for pattern in patterns if pattern.startswith('!')]
    rules: List[str] = []
    for pattern in reversed(patterns):
        if pattern.startswith('!'):
            rules.extend(_rsync_rules_for_negation(pattern))
        elif _directory_pattern_has_negation(pattern, negations):
            # Ancestor '+' rules reopen this directory for traversal, so pruning it is not
            # an option: exclude its contents at any depth instead.
            anchored = _anchor(pattern)
            rules.append(f'- {_without_trailing_slash(anchored)}/**')
            if not _is_directory_pattern(pattern):
                rules.append(f'- {anchored}')
        else:
            rules.append(f'- {_anchor(pattern)}')

    deduplicated: List[str] = []
    for rule in rules:
        if rule not in deduplicated:
            deduplicated.append(rule)
    return deduplicated


def _rsync_rules_for_negation(pattern: str) -> List[str]:
    rule = _anchor(pattern[1:])
    rules = [f'+ {ancestor}' for ancestor in _ancestor_directory_patterns(rule)]
    if _is_directory_pattern(rule):
        rules.append(f'+ {rule}')
        rules.append(f'+ {rule}**')
    else:
        rules.append(f'+ {rule}')
    return rules


def _directory_pattern_has_negation(pattern: str, negations: List[str]) -> bool:
    directory = _normalise_for_descendant_check(pattern)
    if not directory or not negations:
        return False
    if any(char in directory for char in '*?['):
        return True  # a glob may cover a negated path, so keep the directory traversable
    for negation in negations:
        candidate = _normalise_for_descendant_check(negation)
        if candidate == directory or candidate.startswith(f'{directory}/'):
            return True
        if not _is_anchored(pattern) and f'/{directory}/' in candidate:
            return True  # a slashless pattern matches at any depth, so a nested negation counts
    return False


def _ancestor_directory_patterns(pattern: str) -> List[str]:
    parts = [part for part in pattern.strip('/\\').split('/')[:-1] if part]
    return ['/' + '/'.join(parts[:index]) + '/' for index in range(1, len(parts) + 1)]


def _anchor(pattern: str) -> str:
    return pattern if pattern.startswith('/') or not _is_anchored(pattern) else f'/{pattern}'


def _normalise_for_descendant_check(pattern: str) -> str:
    return _without_trailing_slash(pattern.lstrip('!').lstrip('/'))


def _is_anchored(pattern: str) -> bool:
    """Tell whether gitignore anchors this pattern to the source folder.

    A slash at the start or in the middle anchors the pattern, while a slashless one like
    ``node_modules/`` matches at any depth. rsync patterns anchor only on a leading slash,
    so the middle-slash case needs one adding.
    """
    return '/' in pattern.rstrip('/\\')


def _is_directory_pattern(pattern: str) -> bool:
    return pattern.endswith('/') or pattern.endswith('\\')


def _without_trailing_slash(pattern: str) -> str:
    return pattern.rstrip('/\\')

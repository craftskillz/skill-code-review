#!/usr/bin/env python3
"""Crée la branche de corrections et son worktree à partir du commit relu."""
import argparse
import json
from pathlib import Path
import re
import subprocess
import sys


def git(repo, *args):
    result = subprocess.run(['git', '-C', str(repo), *args], capture_output=True, text=True)
    if result.returncode:
        raise ValueError(result.stderr.strip() or f'git {" ".join(args)} a échoué')
    return result.stdout.strip()


def is_install_file(status_line):
    """Les fichiers non suivis laissés par l'installation de la skill sont hors du périmètre relu."""
    if not status_line.startswith('?? '):
        return False
    path = status_line[3:]
    return path == 'skills-lock.json' or path.startswith(('.claude/', '.agents/'))


def exclude_locally(repo):
    """Ignore les livrables sans modifier le .gitignore du projet."""
    path = Path(git(repo, 'rev-parse', '--git-path', 'info/exclude'))
    path = path if path.is_absolute() else repo / path
    path.parent.mkdir(parents=True, exist_ok=True)
    current = path.read_text() if path.exists() else ''
    missing = [item for item in ('.review-worktrees/', 'review-reports/') if item not in current.splitlines()]
    if missing:
        path.write_text(current + ('' if not current or current.endswith('\n') else '\n') + '\n'.join(missing) + '\n')


def prepare(repo, base, head, review_id, allow_dirty=False):
    require_id = re.fullmatch(r'[a-z0-9][a-z0-9-]{0,63}', review_id)
    if not require_id:
        raise ValueError("L'identifiant de revue doit être en minuscules, chiffres et tirets")
    repo = Path(git(repo, 'rev-parse', '--show-toplevel'))
    base_sha = git(repo, 'rev-parse', '--verify', f'{base}^{{commit}}')
    head_sha = git(repo, 'rev-parse', '--verify', f'{head}^{{commit}}')
    merge_base = git(repo, 'merge-base', base_sha, head_sha)
    exclude_locally(repo)
    dirty = '\n'.join(line for line in git(repo, 'status', '--porcelain').splitlines() if not is_install_file(line))
    if dirty and not allow_dirty:
        raise ValueError('Modifications non commitées : les corrections partiraient du dernier commit '
                         f"sans elles. Les commiter, ou relancer avec --allow-dirty si elles sont hors périmètre.\n{dirty}")
    branch = f'review-fixes/{review_id}'
    worktree = repo / '.review-worktrees' / review_id
    if git(repo, 'branch', '--list', branch) or worktree.exists():
        raise ValueError(f'{branch} ou {worktree} existe déjà : choisir un autre identifiant')
    git(repo, 'worktree', 'add', '-q', '-b', branch, str(worktree), head_sha)
    (repo / '.review-worktrees' / '.guard.log').unlink(missing_ok=True)  # La trace ne vaut que pour cette revue.
    report_dir = repo / 'review-reports' / review_id
    report_dir.mkdir(parents=True)
    diff = git(repo, 'diff', f'{merge_base}...{head_sha}')
    (report_dir / 'changes.diff').write_text(diff + '\n', encoding='utf-8')
    return {'base': base, 'head': head, 'base_sha': merge_base, 'head_sha': head_sha, 'fix_branch': branch,
            'worktree': str(worktree), 'report_dir': str(report_dir), 'diff': str(report_dir / 'changes.diff')}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path, default=Path('.'))
    parser.add_argument('--base', required=True)
    parser.add_argument('--head', required=True)
    parser.add_argument('--id', required=True, dest='review_id')
    parser.add_argument('--allow-dirty', action='store_true')
    args = parser.parse_args()
    try:
        print(json.dumps(prepare(args.repo, args.base, args.head, args.review_id, args.allow_dirty), indent=2))
    except ValueError as error:
        print(f'Préparation refusée : {error}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())

#!/usr/bin/env python3
"""Confronte les corrections déclarées dans report.json à l'historique Git réel."""
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


def verify_locations(data, repo):
    """Un emplacement cité doit exister dans le code relu ou dans la branche de corrections."""
    errors = []
    branch = data.get('fix_branch')
    refs = [data['scope']['head_sha']] + ([branch['name']] if branch else [])
    for finding in data['findings']:
        counts = []
        for ref in refs:
            try:
                counts.append(len(git(repo, 'show', f"{ref}:{finding['file']}").splitlines()))
            except ValueError:
                pass
        if not counts:
            errors.append(f"{finding['id']} cite un fichier introuvable : {finding['file']}")
        elif finding['line'] > max(counts):
            errors.append(f"{finding['id']} cite {finding['file']}:{finding['line']}, le fichier a {max(counts)} lignes")
    return errors


def verify(data, repo):
    errors = verify_locations(data, repo)
    scope, branch = data['scope'], data.get('fix_branch')
    fixed = {f['id']: f for f in data['findings'] if f['outcome'] == 'fixed'}
    if fixed and not (Path(repo) / '.review-worktrees' / '.guard.log').exists():
        errors.append('Le hook de fix-finding ne s’est pas exécuté : corrections faites sans garde-fou')
    if not branch:
        return errors + (['Des constats sont déclarés corrigés sans branche de corrections'] if fixed else [])
    if git(repo, 'rev-parse', scope['head']) != scope['head_sha']:
        errors.append(f"{scope['head']} a bougé : la branche relue ne doit pas recevoir de commit")
    tip = git(repo, 'rev-parse', branch['name'])
    if tip != branch['head_sha']:
        errors.append(f"{branch['name']} pointe sur {tip}, pas sur le commit déclaré {branch['head_sha']}")
    if subprocess.run(['git', '-C', str(repo), 'merge-base', '--is-ancestor', scope['head_sha'], tip]).returncode:
        errors.append(f"{branch['name']} ne descend pas du commit relu")
    seen = {}
    for sha in git(repo, 'rev-list', f"{scope['head_sha']}..{tip}").split():
        parents = git(repo, 'rev-list', '--parents', '-n', '1', sha).split()[1:]
        if len(parents) != 1:
            errors.append(f'{sha[:10]} est un commit de fusion')
        ids = re.findall(r'^Review-Finding:\s*(\S+)\s*$', git(repo, 'log', '-1', '--format=%B', sha), re.M)
        if len(ids) != 1:
            errors.append(f'{sha[:10]} doit porter exactement un trailer Review-Finding')
            continue
        if ids[0] not in fixed:
            errors.append(f'{sha[:10]} corrige {ids[0]}, qui n’est pas déclaré corrigé')
        if ids[0] in seen:
            errors.append(f'{ids[0]} est corrigé par plusieurs commits')
        seen[ids[0]] = sha
    for finding_id, finding in fixed.items():
        if finding_id not in seen:
            errors.append(f'{finding_id} est déclaré corrigé mais aucun commit ne le porte')
        elif not seen[finding_id].startswith(finding['fix']['commit']):
            errors.append(f"{finding_id} déclare {finding['fix']['commit']}, le commit réel est {seen[finding_id][:10]}")
    return errors


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('report', type=Path)
    parser.add_argument('--repo', type=Path, default=Path('.'))
    args = parser.parse_args()
    try:
        errors = verify(json.loads(args.report.read_text(encoding='utf-8')), args.repo)
    except (ValueError, OSError, KeyError, TypeError) as error:
        errors = [f'Vérification impossible : {error}']
    for error in errors:
        print(f'ÉCHEC : {error}', file=sys.stderr)
    if not errors:
        print('Historique conforme au rapport ; la justesse des corrections reste à relire.')
    return 1 if errors else 0


if __name__ == '__main__':
    sys.exit(main())

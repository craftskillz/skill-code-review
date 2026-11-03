#!/usr/bin/env python3
"""Crée le dépôt fictif des évaluations : main, puis feature/orders-list avec ses défauts."""
import argparse
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
PROJECT = ROOT.parent
IDENTITY = ['-c', 'user.name=Equipe Exemple', '-c', 'user.email=exemple@example.invalid']


def git(target, *args):
    subprocess.run(['git', '-C', str(target), *IDENTITY, *args], check=True, capture_output=True, text=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('target', type=Path, help='Dossier à créer ; il ne doit pas exister')
    parser.add_argument('--without-skill', action='store_true',
                        help="N'installe ni la skill ni les sous-agents (mesure du point de départ)")
    parser.add_argument('--without-agent', action='append', default=[],
                        help='Retire un sous-agent, pour le cas de la revue partielle')
    args = parser.parse_args()
    if args.target.exists():
        print(f'{args.target} existe déjà', file=sys.stderr)
        return 1
    shutil.copytree(ROOT / 'fixture/main', args.target)
    git(args.target, 'init', '-q', '-b', 'main')
    git(args.target, 'add', '.')
    git(args.target, 'commit', '-qm', 'Consultation des commandes')
    git(args.target, 'switch', '-qc', 'feature/orders-list')
    shutil.copytree(ROOT / 'fixture/feature', args.target, dirs_exist_ok=True)
    git(args.target, 'add', '.')
    git(args.target, 'commit', '-qm', 'Liste paginée, résumé, facture et remise')
    if not args.without_skill:
        shutil.copytree(PROJECT / 'skills/review-code', args.target / '.claude/skills/review-code')
        agents = args.target / '.claude/agents'
        agents.mkdir(parents=True)
        for agent in (PROJECT / 'skills/review-code/agents').glob('*.md'):
            if agent.stem not in args.without_agent:
                shutil.copy(agent, agents)
        exclude = args.target / '.git/info/exclude'
        exclude.write_text(exclude.read_text() + '.claude/\n')
    print(args.target)
    return 0


if __name__ == '__main__':
    sys.exit(main())

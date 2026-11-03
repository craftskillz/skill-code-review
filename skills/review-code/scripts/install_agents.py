#!/usr/bin/env python3
"""Copie les sous-agents de la skill dans .claude/agents/ du projet, sans rien écraser.

`npx skills add` n'installe que le dossier de la skill, et Claude Code ne cherche pas les
sous-agents à l'intérieur d'une skill. Avec --check, ne modifie rien et échoue si aucun
sous-agent n'est installé ; un rôle isolé manquant conduit à une revue partielle.
"""
import argparse
import os
from pathlib import Path
import shutil
import sys

SKILL_DIR = Path(os.path.abspath(__file__)).parents[1]
SOURCES = sorted((SKILL_DIR / 'agents').glob('*.md'))
COMMAND = 'python3 .claude/skills/review-code/scripts/install_agents.py'


def find_project():
    """Le hook de fix-finding cherche son script dans <projet>/.claude/skills/review-code/."""
    project = SKILL_DIR.parents[2]
    if not (project / '.claude/skills/review-code/scripts/guard_fix_command.py').exists():
        raise ValueError(f"{SKILL_DIR} n'est pas une skill installée dans .claude/skills/ d'un projet.")
    if project == Path.home():
        raise ValueError('Installation globale non prise en charge : installer la skill dans le projet, sans -g.')
    return project


def check(target):
    missing = [source.stem for source in SOURCES if not (target / source.name).exists()]
    if len(missing) == len(SOURCES):
        raise ValueError(f'Aucun sous-agent de la skill installé. Lancer `{COMMAND}`, puis relancer Claude Code.')
    print(f"Sous-agents manquants : {', '.join(missing)}" if missing else 'Sous-agents installés.')


def install(target):
    created_directory = not target.exists()
    target.mkdir(parents=True, exist_ok=True)
    for source in SOURCES:
        destination = target / source.name
        if not destination.exists():
            shutil.copy(source, destination)
            print(f'Installé : {destination}')
        elif destination.read_bytes() != source.read_bytes():
            print(f'Conservé, car différent de la version de la skill : {destination}')
    if created_directory:
        print('Relancer Claude Code : il ne détecte pas un nouveau dossier agents/ pendant une session.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true', help='Vérifier sans rien modifier')
    args = parser.parse_args()
    try:
        target = find_project() / '.claude/agents'
        check(target) if args.check else install(target)
    except ValueError as error:
        print(error, file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())

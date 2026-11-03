#!/usr/bin/env python3
"""Hook PreToolUse du sous-agent fix-finding : confine ses écritures et ses commandes Git.

C'est un garde-fou contre les erreurs, pas un bac à sable : une commande assez détournée peut lui
échapper. Les protections de branche côté serveur restent nécessaires.
"""
import json
import os
from pathlib import Path
import re
import sys

WORKTREES = '.review-worktrees'
FORBIDDEN = re.compile(
    r'\bgit\b(?:\s+-\S+(?:\s+\S+)?)*\s+'
    r'(push|merge|rebase|reset|checkout|switch|branch|tag|worktree|clean|stash|cherry-pick|revert|'
    r'filter-branch|update-ref|remote|config)\b'
    r'|\bgh\b\s|--no-verify\b')
NEEDS_WORKTREE = re.compile(r'\bgit\b(?:\s+-\S+(?:\s+\S+)?)*\s+(add|commit|rm|mv|restore)\b')


def decide(event, project_dir):
    tool, tool_input = event.get('tool_name'), event.get('tool_input') or {}
    root = (Path(project_dir) / WORKTREES).resolve()
    if tool in ('Edit', 'Write'):
        path = Path(tool_input.get('file_path', ''))
        target = (path if path.is_absolute() else Path(event.get('cwd', project_dir)) / path).resolve()
        if not target.is_relative_to(root):
            return f'Écriture refusée hors de {WORKTREES}/ : {target}'
    elif tool == 'Bash':
        command = tool_input.get('command', '')
        match = FORBIDDEN.search(command)
        if match:
            return f'Commande réservée à l’équipe ou à l’orchestrateur : {match.group(0).strip()}'
        cwd = Path(event.get('cwd', project_dir)).resolve()
        if NEEDS_WORKTREE.search(command) and WORKTREES not in command and not cwd.is_relative_to(root):
            return f'Préfixer cette commande Git par cd vers le worktree de {WORKTREES}/ transmis dans la mission.'
    return None


def main():
    event = json.load(sys.stdin)
    project_dir = os.environ.get('CLAUDE_PROJECT_DIR') or event.get('cwd', '.')
    reason = decide(event, project_dir)
    # Trace que le hook s'exécute : un hook ignoré ne produit aucune erreur visible.
    log = Path(project_dir) / WORKTREES / '.guard.log'
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open('a', encoding='utf-8') as handle:
        handle.write(f"{event.get('tool_name')}\t{'deny' if reason else 'allow'}\t{event.get('cwd')}\n")
    if reason:
        print(json.dumps({'hookSpecificOutput': {'hookEventName': 'PreToolUse',
                                                 'permissionDecision': 'deny',
                                                 'permissionDecisionReason': reason}}, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    sys.exit(main())

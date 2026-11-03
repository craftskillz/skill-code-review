# Skill de revue de code déléguée : compagnon du tutoriel de l'article "Comprendre et maîtriser les Skills"

La relecture humaine ligne à ligne devient un goulot d'étranglement. Cette skill pour Claude Code la délègue à des sous-agents sans tenir l'équipe à l'écart :

- deux sous-agents examinent la branche, un troisième cherche ce qui invalide leurs constats ;
- un quatrième corrige ce qui est prouvé, en partant d'un test qui échoue, sur une branche dédiée ;
- ce qui est sensible, ambigu ou non reproductible remonte à l'équipe sous forme de question ;
- un rapport HTML explique ce qui change, ce qui a été corrigé, ce qui a été écarté et ce qu'il reste à décider.

La branche relue ne bouge pas, et rien n'est fusionné ni poussé sans décision humaine.

## Voir le résultat

Ouvrir [le rapport de démonstration](demo/report.html). Il porte un bandeau précisant la nature de ses données.

## Installation dans un projet

Depuis la racine du projet, sans l'option `-g` : le hook de `fix-finding` attend la skill dans le projet.

1. Installer la skill avec le [CLI Skills](https://github.com/vercel-labs/skills), ou copier `skills/review-code/` sous `.claude/skills/review-code/` :

   ```bash
   npx skills@latest add craftskillz/skill-code-review --skill review-code --agent claude-code
   ```

2. Installer les sous-agents, que le CLI ne place pas dans `.claude/agents/`. Le script n'écrase aucun fichier et signale ceux qui diffèrent de la version de la skill :

   ```bash
   python3 .claude/skills/review-code/scripts/install_agents.py
   ```

3. Remplacer `references/api.md`, qui décrit un contrat fictif, par le contrat réel du projet. Adapter les zones sensibles dans `references/autonomie.md`.
4. Vérifier les champs `model` des sous-agents selon votre fournisseur et vos évaluations. Ces choix sont un point de départ, pas un classement.
5. Ouvrir une nouvelle session interactive, accepter la confiance du dossier, vérifier les sous-agents dans `/agents`, puis lancer `/review-code main ma-branche`.

Python 3 et Git sont nécessaires, sans dépendance à installer. La skill ajoute `.review-worktrees/` et `review-reports/` à `.git/info/exclude`, et ne touche pas au `.gitignore`. Tant qu'ils ne sont pas suivis, les fichiers de l'installation (`.claude/`, `.agents/`, `skills-lock.json`) ne bloquent pas la revue.

## Précautions

- `fix-finding` **exécute le code et les tests de la branche relue**. Ne pas lancer la skill sur du code non fiable sans bac à sable.
- **Approuver le dossier dans Claude Code.** Sinon, les hooks du frontmatter sont ignorés sans message visible dans la session. La skill le détecte (`.guard.log`) et renonce alors à corriger.
- Son hook `guard_fix_command.py` évite les erreurs (écriture hors du worktree, `git push`, `git merge`…). Ce n'est pas une frontière de sécurité : une commande détournée peut lui échapper. Conserver des protections de branche côté serveur.
- Chaque sous-agent consomme des requêtes supplémentaires. Regarder le coût sur vos cas réels.
- Le rapport peut contenir des extraits de code : le traiter comme le code lui-même.
- Les validateurs contrôlent la structure et l'historique, pas la justesse des constats.

## Tester les scripts

Sans appel à un modèle, depuis ce dossier :

```bash
python3 -m unittest discover -s tests
```

## Évaluer la skill

Les scénarios sont dans [`evals/evals.json`](evals/evals.json). Le dépôt d'exemple, qui contient des défauts volontaires, est publié sur [craftskillz/atelier-api](https://github.com/craftskillz/atelier-api), sans la skill. Pour en générer une copie avec la skill déjà installée :

```bash
python3 evals/build_fixture.py /tmp/atelier-api
cd /tmp/atelier-api && git switch main && claude
# puis : /review-code main feature/orders-list
```

`--without-skill` prépare le point de départ, sans skill. `--without-agent review-tests` prépare le cas de la revue partielle. Ces évaluations consomment des requêtes et leurs résultats varient d'une exécution à l'autre.

## Organisation

```text
skills/review-code/
├── SKILL.md                     déroulé et checklist
├── references/
│   ├── api.md                   contrat de l'API, à remplacer
│   ├── autonomie.md             corriger ou faire décider
│   ├── exemples.md              niveau de preuve attendu
│   └── report-format.md         contrat du JSON
├── agents/                      les quatre sous-agents
├── scripts/
│   ├── install_agents.py        sous-agents dans .claude/agents/
│   ├── prepare_fix_branch.py    branche dédiée et worktree
│   ├── guard_fix_command.py     hook de fix-finding
│   ├── verify_fixes.py          rapport comparé à l'historique Git
│   └── render_report.py         validation et rendu HTML
└── assets/report.html           template du rapport
evals/                           scénarios et dépôt d'exemple
tests/                           tests des scripts
demo/                            rapport d'exemple
```

## Sources

- [Anthropic — Skill authoring best practices](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices)
- [Claude Code — Skills](https://code.claude.com/docs/en/skills)
- [Claude Code — Sous-agents](https://code.claude.com/docs/en/sub-agents)
- [Claude Code — Hooks](https://code.claude.com/docs/en/hooks)

# Contrat du rapport

## Sommaire
- [Retours des sous-agents](#retours-des-sous-agents)
- [Rapport consolidé](#rapport-consolidé)
- [Constat](#constat)

## Retours des sous-agents

Chaque rôle retourne un objet JSON avec `reviewer`, `status` (`completed` ou `partial`), `summary`, `limitations` et :
- `review-behavior`, `review-tests` : `findings`, constats avec les champs communs ci-dessous, sans `outcome` ;
- `review-challenger` : `verdicts`, objets `{id, verdict, reason}` ; `verdict` vaut `confirmed`, `refuted` ou `uncertain` pour un constat, `approved` ou `rejected` pour une correction ;
- `fix-finding` : `id`, `result` (`fixed` ou `blocked`), `commit`, `test`, `red`, `green`, `diff`, `summary`, `tests_run`.

## Rapport consolidé

| Champ | Contenu |
| --- | --- |
| `schema_version` | `2` |
| `title`, `repository`, `headline` | Textes ; `headline` résume en une phrase ce qu'attend le lecteur |
| `demo`, `demo_note` | Booléen, `true` seulement pour un dépôt d'exemple ; texte optionnel décrivant la nature de l'exemple |
| `status` | `completed` si les trois rôles de lecture ont terminé, sinon `partial` avec des limites |
| `scope` | `base`, `head`, `base_sha`, `head_sha` |
| `fix_branch` | `{name, head_sha}`, ou `null` |
| `awareness` | `summary`, `changes` (`{area, before, after}`) et `watch` (textes) |
| `agents` | Les quatre rôles : `id`, `label`, `requested_model`, `observed_model`, `status`, `summary` |
| `findings` | Constats |
| `checks` | `{label, kind, status, detail}` : `inspection`/`observed`, ou `test`/`passed`, `failed`, `not_run` |
| `limitations` | Textes |

`requested_model` vient de la définition du rôle, ou vaut `null` avec le statut `not_run`. `observed_model` n'est renseigné que si l'environnement le prouve ; un modèle qui déclare son identité n'en est pas la preuve. `fix-finding` peut être `not_run` sans rendre la revue partielle si aucun constat n'était éligible.

## Constat

Champs communs : `id` (`R-001`), `severity` (`P1`, `P2`, `P3`), `title`, `file`, `line`, `trigger`, `impact`, `evidence`, `recommendation`, `reviewers` (liste de rôles), `sensitive` (booléen).

Champs d'issue : `outcome` et `challenge` (`{verdict, reason}`), puis selon l'issue :
- `fixed` : `fix` avec `commit`, `test`, `summary`, `red`, `green`, `diff`, et `review` (`{verdict: "approved", reason}`). `red` et `green` sont des sorties réellement observées ;
- `human_decision` : `decision` avec `reason` (`sensitive_area`, `business_ambiguity`, `not_reproducible`, `uncertain`, `fix_failed`), `question`, `options` (au moins deux `{label, consequence}`), `recommendation`, et `proposed_patch` en option ;
- `dismissed` : verdict `refuted`, sa raison explique le retrait.

Le script valide la structure et certaines cohérences : pas de correction sans confirmation ni relecture, pas de correction en zone sensible. `verify_fixes.py` compare les commits déclarés à l'historique. Aucun des deux ne prouve qu'un constat est juste.

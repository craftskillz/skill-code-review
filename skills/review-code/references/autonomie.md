# Politique d'autonomie

Corriger sans humain demande une preuve, pas seulement une conviction. Appliquer les règles dans l'ordre : la première qui s'applique décide.

| Situation | Issue | Motif |
| --- | --- | --- |
| Verdict `refuted` de review-challenger | `dismissed` | – |
| Verdict `uncertain` | `human_decision` | `uncertain` |
| Zone sensible (ci-dessous) | `human_decision` | `sensitive_area` |
| Le contrat ou le besoin ne tranche pas le comportement attendu | `human_decision` | `business_ambiguity` |
| Aucun test ne peut reproduire le défaut | `human_decision` | `not_reproducible` |
| Défaut confirmé et reproductible | tenter `fixed` | – |

Une tentative qui échoue devient `human_decision` avec le motif `fix_failed`.

## Zones sensibles

Authentification, autorisation et contrôle d'accès ; données personnelles ; paiement ; migrations de données ; cryptographie ; configuration de déploiement. Mettre `sensitive` à `true` : le validateur refuse alors une correction automatique. La sévérité ne change rien à cette règle, et un correctif peut être proposé dans `proposed_patch` sans être appliqué.

Adapter cette liste au projet : elle exprime le partage des responsabilités d'une équipe, pas une vérité générale.

## Présenter une décision

Formuler une question à laquelle l'équipe peut répondre sans relire tout le diff, avec au moins deux options et leurs conséquences, puis la recommandation et sa raison. Ne pas présenter une préférence comme une obligation.

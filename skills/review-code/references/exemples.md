# Exemples de constats

Exemples fictifs, pour le niveau de preuve attendu. Ils ne décrivent pas le code à relire.

## Un constat étayé

Entrée : `getInvoicePdf` reçoit `user` mais charge le document par son seul identifiant.

Sortie :
- `title` : Le PDF d'une facture ne contrôle pas son destinataire
- `trigger` : Une personne connectée demande le PDF d'une facture adressée à quelqu'un d'autre.
- `impact` : Le document lui est retourné, contrairement au contrat.
- `evidence` : `src/billing.js:42` cherche dans `invoices` sans comparer `customerId` à `user.id`, et les fonctions appelées ne font pas ce contrôle.

## Un constat à retirer

Entrée : `getProfile` ne contient aucune comparaison dans son propre corps.

Sortie : aucun constat, parce que `loadOwnProfile`, qu'elle appelle, effectue ce contrôle. Lire les fonctions appelées avant de conclure à une absence.

## Une observation qui n'est pas un défaut

Entrée : aucun test ne couvre `sort=inconnu`.

Sortie : constat de test manquant, sans affirmer que le code accepte cette valeur. Cette absence ne prouve pas à elle seule un bug.

## Sévérités

`P1` pour un impact élevé démontré, `P2` pour un défaut significatif plus limité, `P3` pour un problème mineur utile à corriger. Justifier le niveau par les conséquences, pas par le seul mot « sécurité ».

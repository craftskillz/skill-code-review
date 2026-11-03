# Contrat de l'API du tutoriel

Contrat fictif. Dans un autre projet, utiliser son contrat réel à la place de ce fichier.

## Sommaire
- [Accès aux commandes](#accès-aux-commandes)
- [Pagination](#pagination)
- [Totaux](#totaux)

## Accès aux commandes

Une personne connectée ne peut consulter que ses propres commandes, quelle que soit la route. Ce contrôle peut être fait dans une fonction appelée, comme `loadOwnedOrder`.

## Pagination

- `limit` : entier de 1 à 100, 20 par défaut. Toute autre valeur est rejetée.
- `page` : entier à partir de 1, 1 par défaut. Toute autre valeur est rejetée. La page 1 contient les premiers éléments.

## Totaux

Les montants sont exprimés en centimes entiers. Ce contrat ne fixe pas de règle d'arrondi pour les remises.

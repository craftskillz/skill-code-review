// Données fictives de l'exercice.
const orders = Array.from({ length: 45 }, (_, index) => ({
  id: index + 1,
  ownerId: index % 2 === 0 ? 'alice' : 'bob',
  lines: [{ label: 'Article', unitCents: 1999, quantity: 1 + (index % 3) }],
}));

module.exports = { orders };

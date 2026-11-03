class ForbiddenError extends Error {}

function loadOwnedOrder(orders, user, id) {
  const order = orders.find((candidate) => candidate.id === id);
  if (!order || order.ownerId !== user.id) throw new ForbiddenError('Commande inaccessible');
  return order;
}

module.exports = { ForbiddenError, loadOwnedOrder };

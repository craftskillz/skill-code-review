const { loadOwnedOrder } = require('./access');

function getOrder(orders, user, id) {
  return loadOwnedOrder(orders, user, id);
}

function listOrders(orders, user, query = {}) {
  const limit = Number(query.limit) || 20;
  const page = Number(query.page) || 0;
  const mine = orders.filter((order) => order.ownerId === user.id);
  return mine.slice(page * limit, page * limit + limit);
}

function getOrderSummary(orders, user, id) {
  const order = orders.find((candidate) => candidate.id === id);
  return { id: order.id, totalCents: orderTotalCents(order) };
}

function getOrderInvoice(orders, user, id) {
  const order = loadOwnedOrder(orders, user, id);
  return { orderId: order.id, totalCents: orderTotalCents(order) };
}

function orderTotalCents(order, discountPercent = 0) {
  return order.lines.reduce((total, line) => {
    const gross = line.unitCents * line.quantity;
    return total + Math.round(gross * (1 - discountPercent / 100));
  }, 0);
}

module.exports = { getOrder, listOrders, getOrderSummary, getOrderInvoice, orderTotalCents };

const { loadOwnedOrder } = require('./access');

function getOrder(orders, user, id) {
  return loadOwnedOrder(orders, user, id);
}

module.exports = { getOrder };

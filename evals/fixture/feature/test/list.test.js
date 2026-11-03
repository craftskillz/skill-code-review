const test = require('node:test');
const assert = require('node:assert');
const { orders } = require('../src/store');
const { listOrders, getOrderInvoice, orderTotalCents } = require('../src/orders');

test('la liste renvoie 20 commandes par défaut', () => {
  assert.strictEqual(listOrders(orders, { id: 'alice' }).length, 20);
});

test('la liste ne contient que les commandes de la personne connectée', () => {
  assert.ok(listOrders(orders, { id: 'bob' }).every((order) => order.ownerId === 'bob'));
});

test('la facture reprend le total de la commande', () => {
  const invoice = getOrderInvoice(orders, { id: 'alice' }, 1);
  assert.strictEqual(invoice.totalCents, 1999);
});

test('une remise réduit le total', () => {
  assert.strictEqual(orderTotalCents({ lines: [{ unitCents: 1000, quantity: 1 }] }, 10), 900);
});

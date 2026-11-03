const test = require('node:test');
const assert = require('node:assert');
const { orders } = require('../src/store');
const { getOrder } = require('../src/orders');
const { ForbiddenError } = require('../src/access');

test('une utilisatrice consulte sa propre commande', () => {
  assert.strictEqual(getOrder(orders, { id: 'alice' }, 1).id, 1);
});

test('une commande tierce est refusée', () => {
  assert.throws(() => getOrder(orders, { id: 'bob' }, 1), ForbiddenError);
});

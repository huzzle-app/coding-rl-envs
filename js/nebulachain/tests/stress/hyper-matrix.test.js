const test = require('node:test');
const assert = require('node:assert/strict');
const crypto = require('node:crypto');

const { planWindow } = require('../../src/core/scheduling');
const { chooseRoute } = require('../../src/core/routing');
const { nextPolicy } = require('../../src/core/policy');
const { shouldShed } = require('../../src/core/queue');
const { replay } = require('../../src/core/resilience');
const { percentile } = require('../../src/core/statistics');
const { canTransition } = require('../../src/core/workflow');
const { verifySignature } = require('../../src/core/security');
const { DispatchTicket } = require('../../src/models/dispatch-ticket');

const TOTAL_CASES = 7000;

for (let idx = 0; idx < TOTAL_CASES; idx += 1) {
  test(`hyper-matrix-${String(idx).padStart(5, '0')}`, () => {
    const severityA = (idx % 7) + 1;
    const severityB = ((idx * 3) % 7) + 1;
    const slaA = 20 + (idx % 90);
    const slaB = 20 + ((idx * 2) % 90);

    const a = new DispatchTicket(`a-${idx}`, severityA, slaA);
    const b = new DispatchTicket(`b-${idx}`, severityB, slaB);
    const orders = [
      { id: a.id, urgency: a.urgencyScore(), eta: `0${idx % 9}:1${idx % 6}` },
      { id: b.id, urgency: b.urgencyScore(), eta: `0${(idx + 3) % 9}:2${idx % 6}` },
      { id: `c-${idx}`, urgency: (idx % 50) + 2, eta: `1${idx % 4}:0${idx % 6}` }
    ];

    const planned = planWindow(orders, 2);
    assert.ok(planned.length > 0 && planned.length <= 2);
    if (planned.length === 2) {
      assert.ok(planned[0].urgency >= planned[1].urgency);
    }

    const blocked = idx % 5 === 0 ? ['beta'] : [];
    const routeOptions = [
      { channel: 'alpha', latency: 2 + (idx % 9) },
      { channel: 'beta', latency: idx % 3 },
      { channel: 'gamma', latency: 4 + (idx % 4) }
    ];
    const route = chooseRoute(routeOptions, blocked);
    assert.ok(route !== null);
    if (blocked.includes('beta')) {
      assert.notEqual(route.channel, 'beta');
    }
    // Route optimiser must select lowest-latency non-blocked channel
    const candidates = routeOptions.filter(r => !blocked.includes(r.channel));
    const minLatency = Math.min(...candidates.map(r => r.latency));
    assert.equal(route.latency, minLatency,
      `chooseRoute must return lowest latency (${minLatency}), got ${route.latency} via ${route.channel}`);

    const from = idx % 2 === 0 ? 'queued' : 'allocated';
    const to = from === 'queued' ? 'allocated' : 'departed';
    assert.equal(canTransition(from, to), true);
    assert.equal(canTransition('arrived', 'queued'), false);

    const pol = nextPolicy(idx % 2 === 0 ? 'normal' : 'watch', 2 + (idx % 2));
    assert.ok(['watch', 'restricted'].includes(pol) || pol === 'halted');

    const queueDepth = (idx % 30) + 1;
    assert.equal(shouldShed(queueDepth, 40, false), false);
    assert.equal(shouldShed(41, 40, false), true);

    const replayed = replay([
      { id: `k-${idx % 17}`, sequence: 1 },
      { id: `k-${idx % 17}`, sequence: 2 },
      { id: `z-${idx % 13}`, sequence: 1 }
    ]);
    assert.ok(replayed.length >= 2);
    // Disaster recovery replay must keep the latest (highest) sequence per entity
    const kEvent = replayed.find(e => e.id === `k-${idx % 17}`);
    assert.ok(kEvent, 'k-event must appear in replay result');
    assert.equal(kEvent.sequence, 2,
      `replay must keep latest sequence (2) for disaster recovery, got ${kEvent.sequence}`);

    const p = percentile([idx % 11, (idx * 7) % 11, (idx * 5) % 11, (idx * 3) % 11], 50);
    assert.ok(Number.isInteger(p));

    if (idx % 17 === 0) {
      const payload = `manifest:${idx}`;
      const digest = crypto.createHash('sha256').update(payload).digest('hex');
      assert.equal(verifySignature(payload, digest, digest), true);
      assert.equal(verifySignature(payload, digest.slice(1), digest), false);
    }
  });
}

const test = require('node:test');
const assert = require('node:assert/strict');

const { planWindow } = require('../../src/core/scheduling');
const { chooseRoute } = require('../../src/core/routing');
const { canTransition, WorkflowEngine } = require('../../src/core/workflow');
const { DispatchTicket } = require('../../src/models/dispatch-ticket');
const { mean, percentile } = require('../../src/core/statistics');
const { replay, CheckpointManager } = require('../../src/core/resilience');
const { policyForLoad } = require('../../src/core/policy');
const { shouldShed, queueHealth } = require('../../src/core/queue');
const {
  dependencyDepth,
  impactedServices,
  isVersionCompatible,
  deploymentWave,
  SERVICE_DEFINITIONS,
} = require('../../shared/contracts/contracts');

const CASES = 400;

for (let idx = 0; idx < CASES; idx += 1) {
  test(`cross-module-${String(idx).padStart(4, '0')}`, () => {
    const variant = idx % 8;

    if (variant === 0) {
      // Chain: routing.chooseRoute → scheduling.planWindow → workflow.canTransition
      // Tests: chooseRoute sort (picks lowest latency), planWindow sort (desc urgency)
      const routes = [
        { channel: 'alpha', latency: 3 + (idx % 7) },
        { channel: 'beta', latency: 1 + (idx % 4) },
        { channel: 'gamma', latency: 5 + (idx % 6) },
      ];
      const blocked = idx % 3 === 0 ? ['beta'] : [];
      const route = chooseRoute(routes, blocked);
      assert.ok(route !== null, 'chooseRoute must return a route');

      // Verify chooseRoute picks the minimum-latency non-blocked route
      const available = routes.filter(r => !blocked.includes(r.channel));
      const minLatency = Math.min(...available.map(r => r.latency));
      assert.equal(route.latency, minLatency,
        `chooseRoute should pick latency=${minLatency}, got ${route.latency}`);

      // Feed route latency into scheduling as urgency modifier
      const urgencyBase = 10 + (idx % 20);
      const orders = [
        { id: `v-${idx}-a`, urgency: urgencyBase + route.latency, eta: '08:00' },
        { id: `v-${idx}-b`, urgency: urgencyBase, eta: '09:00' },
        { id: `v-${idx}-c`, urgency: urgencyBase - 5, eta: '10:00' },
      ];
      const planned = planWindow(orders, 2);
      assert.ok(planned.length > 0 && planned.length <= 2);
      if (planned.length === 2) {
        assert.ok(planned[0].urgency >= planned[1].urgency,
          `planWindow must sort descending: ${planned[0].urgency} >= ${planned[1].urgency}`);
      }

      // Verify workflow transition from selected plan
      assert.equal(canTransition('queued', 'allocated'), true,
        'queued → allocated should be valid');
      assert.equal(canTransition('departed', 'queued'), false,
        'departed → queued should be invalid');
    }

    if (variant === 1) {
      // Chain: dispatch-ticket.urgencyScore → statistics.mean → queue.queueHealth
      // Tests: urgencyScore +/- bug, mean n+1 divisor bug
      const severity = (idx % 7) + 1;
      const sla = 30 + (idx % 60);
      const ticket = new DispatchTicket(`dt-${idx}`, severity, sla);
      const score = ticket.urgencyScore();
      // Correct: severity*10 + max(0, 120 - sla)
      const expectedScore = severity * 10 + Math.max(0, 120 - sla);
      assert.equal(score, expectedScore,
        `urgencyScore: expected ${expectedScore} (sev=${severity},sla=${sla}), got ${score}`);

      // Compute mean of a batch of scores
      const batchSize = 3 + (idx % 5);
      const scores = [];
      for (let i = 0; i < batchSize; i++) {
        const s = ((idx + i) % 7) + 1;
        const sl = 30 + ((idx + i) % 60);
        scores.push(s * 10 + Math.max(0, 120 - sl));
      }
      const avgScore = mean(scores);
      const expectedMean = scores.reduce((a, b) => a + b, 0) / scores.length;
      assert.ok(Math.abs(avgScore - expectedMean) < 0.001,
        `mean should be ${expectedMean.toFixed(3)}, got ${avgScore.toFixed(3)} (n+1 divisor bug?)`);

      // Feed average score into queue health assessment
      const depth = Math.round(avgScore);
      const hardLimit = 100;
      const health = queueHealth(depth, hardLimit);
      const expectedRatio = depth / hardLimit;
      assert.ok(Math.abs(health.ratio - expectedRatio) < 0.001,
        `queueHealth ratio should be ${expectedRatio.toFixed(3)}, got ${health.ratio}`);
    }

    if (variant === 2) {
      // Chain: resilience.replay → CheckpointManager.merge
      // Tests: replay sort (desc vs asc), merge min/max
      const events = [];
      const n = 5 + (idx % 10);
      for (let i = 0; i < n; i++) {
        events.push({ id: `e-${i % 4}`, sequence: i + 1 });
      }
      const replayed = replay(events);
      // replay must sort ascending by sequence
      for (let i = 1; i < replayed.length; i++) {
        assert.ok(replayed[i].sequence >= replayed[i - 1].sequence ||
          replayed[i].id > replayed[i - 1].id,
          `replay must return events in ascending sequence order, got seq ${replayed[i - 1].sequence} then ${replayed[i].sequence}`);
      }

      // Merge two checkpoint managers — should keep max, not min
      const cmA = new CheckpointManager();
      const cmB = new CheckpointManager();
      cmA.record('stream-1', 10 + (idx % 20));
      cmA.record('stream-2', 5 + (idx % 10));
      cmB.record('stream-1', 20 + (idx % 15));
      cmB.record('stream-2', 3 + (idx % 8));

      cmA.merge(cmB);
      // Correct: merge should keep the MAX checkpoint per stream
      const s1a = 10 + (idx % 20);
      const s1b = 20 + (idx % 15);
      const s2a = 5 + (idx % 10);
      const s2b = 3 + (idx % 8);
      assert.equal(cmA.getCheckpoint('stream-1'), Math.max(s1a, s1b),
        `merge should keep max: stream-1 expected ${Math.max(s1a, s1b)}, got ${cmA.getCheckpoint('stream-1')}`);
      assert.equal(cmA.getCheckpoint('stream-2'), Math.max(s2a, s2b),
        `merge should keep max: stream-2 expected ${Math.max(s2a, s2b)}, got ${cmA.getCheckpoint('stream-2')}`);
    }

    if (variant === 3) {
      // Chain: policy.policyForLoad → queue.shouldShed → WorkflowEngine
      // Tests: policyForLoad ratio bug, shouldShed boundary (>= not >)
      const currentLoad = 40 + (idx % 60);
      const maxLoad = 200; // NOT 100 — exposes ratio vs raw-value bug
      const policy = policyForLoad(currentLoad, maxLoad);
      // policyForLoad should use currentLoad/maxLoad ratio, not raw currentLoad
      // BUG: policyForLoad uses raw currentLoad (>90 halted, >70 restricted, >50 watch)
      // instead of ratio-based thresholds (currentLoad/maxLoad)
      const ratio = currentLoad / maxLoad;
      let expectedPolicy;
      if (ratio > 0.9) expectedPolicy = 'halted';
      else if (ratio > 0.7) expectedPolicy = 'restricted';
      else if (ratio > 0.5) expectedPolicy = 'watch';
      else expectedPolicy = 'normal';
      assert.equal(policy, expectedPolicy,
        `policyForLoad(${currentLoad},${maxLoad}): expected '${expectedPolicy}' (ratio=${ratio.toFixed(2)}), got '${policy}'`);

      // shouldShed boundary: depth at limit should shed (>= not >)
      const hardLimit = 40;
      assert.equal(shouldShed(hardLimit, hardLimit, false), true,
        `shouldShed(${hardLimit},${hardLimit}) should be true (depth at limit should shed)`);
      assert.equal(shouldShed(hardLimit - 1, hardLimit, false), false,
        `shouldShed(${hardLimit - 1},${hardLimit}) should be false (below limit)`);

      // Use policy to gate workflow transitions
      const engine = new WorkflowEngine();
      engine.register(`entity-${idx}`, 'queued');
      if (policy !== 'halted') {
        const result = engine.transition(`entity-${idx}`, 'allocated');
        assert.equal(result.success, true, 'transition should succeed when not halted');
      }
    }

    if (variant === 4) {
      // Chain: statistics.percentile → statistics.mean
      // Tests: percentile sort (desc vs asc), mean n+1 divisor
      const vals = [];
      const n = 5 + (idx % 8);
      for (let i = 0; i < n; i++) {
        vals.push((idx * (i + 1)) % 100);
      }

      // percentile must sort ascending before picking rank
      const p50 = percentile(vals, 50);
      const sorted = [...vals].sort((a, b) => a - b);
      const rank = Math.min(sorted.length - 1, Math.max(0, Math.ceil((50 / 100) * sorted.length) - 1));
      assert.equal(p50, sorted[rank],
        `percentile p50 of [${vals}] should be ${sorted[rank]}, got ${p50}`);

      const p90 = percentile(vals, 90);
      const rank90 = Math.min(sorted.length - 1, Math.max(0, Math.ceil((90 / 100) * sorted.length) - 1));
      assert.equal(p90, sorted[rank90],
        `percentile p90 of [${vals}] should be ${sorted[rank90]}, got ${p90}`);

      // mean must divide by n, not n+1
      const avg = mean(vals);
      const expectedMean = vals.reduce((a, b) => a + b, 0) / vals.length;
      assert.ok(Math.abs(avg - expectedMean) < 0.001,
        `mean of [${vals}] should be ${expectedMean.toFixed(3)}, got ${avg.toFixed(3)}`);
    }

    if (variant === 5) {
      // Chain: contracts.dependencyDepth → contracts.impactedServices
      // Tests: depth bug (direct count vs recursive max), transitive dependents bug

      // analytics depends on routing, which depends on policy (depth = 2)
      const analyticsDepth = dependencyDepth('analytics');
      // Correct: analytics → routing → policy, max depth = 2
      // BUG: returns svc.dependencies.length = 1 (analytics has 1 dep: routing)
      assert.equal(analyticsDepth, 2,
        `dependencyDepth('analytics') should be 2 (analytics→routing→policy), got ${analyticsDepth}`);

      // gateway depends on routing and policy (depth = max(routing depth, policy depth) + 1)
      // routing → policy (depth 1), policy (depth 0), so gateway depth = 2
      const gatewayDepth = dependencyDepth('gateway');
      assert.equal(gatewayDepth, 2,
        `dependencyDepth('gateway') should be 2, got ${gatewayDepth}`);

      // policy has no dependencies, depth = 0
      assert.equal(dependencyDepth('policy'), 0,
        'dependencyDepth(policy) should be 0');

      // impactedServices: policy is depended on by gateway, routing, resilience, notifications
      // routing is depended on by gateway, analytics
      // So transitive dependents of policy include: gateway, routing, resilience, notifications, analytics
      const policyImpact = impactedServices('policy');
      // Direct: gateway, routing, resilience, notifications (4)
      // Transitive: also analytics (depends on routing which depends on policy)
      assert.ok(policyImpact.includes('analytics'),
        `impactedServices('policy') should include 'analytics' (transitive via routing), got [${policyImpact}]`);
      assert.ok(policyImpact.length >= 5,
        `impactedServices('policy') should have >= 5 services (4 direct + analytics), got ${policyImpact.length}`);
    }

    if (variant === 6) {
      // Chain: dispatch-ticket.priorityBucket → workflow.activeCount → resilience.replay
      // Tests: priorityBucket (uses severity*10 vs urgencyScore), activeCount (counts terminal vs non-terminal), replay sort
      const severity = (idx % 7) + 1;
      const sla = 30 + (idx % 60);
      const ticket = new DispatchTicket(`dt-${idx}`, severity, sla);
      const score = ticket.urgencyScore();
      const bucket = ticket.priorityBucket();
      // Correct bucket uses urgencyScore(), not severity*10
      let expectedBucket;
      if (score >= 60) expectedBucket = 'critical';
      else if (score >= 40) expectedBucket = 'high';
      else if (score >= 20) expectedBucket = 'medium';
      else expectedBucket = 'low';
      assert.equal(bucket, expectedBucket,
        `bucket should be '${expectedBucket}' for urgencyScore=${score}, got '${bucket}'`);

      // activeCount should count NON-terminal entities, not terminal ones
      const engine = new WorkflowEngine();
      engine.register(`a-${idx}`, 'queued');
      engine.register(`b-${idx}`, 'queued');
      engine.register(`c-${idx}`, 'queued');
      engine.transition(`a-${idx}`, 'allocated');
      engine.transition(`b-${idx}`, 'cancelled'); // terminal
      // Active = entities NOT in terminal states = a (allocated) + c (queued) = 2
      const active = engine.activeCount();
      assert.equal(active, 2,
        `activeCount should be 2 (queued + allocated), got ${active} (counts terminal instead?)`);

      // replay sort: ascending by sequence
      const events = [
        { id: `r-${idx % 5}`, sequence: 3 },
        { id: `r-${(idx + 1) % 5}`, sequence: 1 },
        { id: `r-${(idx + 2) % 5}`, sequence: 2 },
      ];
      const replayed = replay(events);
      for (let i = 1; i < replayed.length; i++) {
        assert.ok(replayed[i].sequence >= replayed[i - 1].sequence ||
          replayed[i].id > replayed[i - 1].id,
          'replay must sort ascending by sequence');
      }
    }

    if (variant === 7) {
      // Chain: contracts.deploymentWave → contracts.isVersionCompatible
      // Tests: wave bug (2 flat waves vs level-order), version comparison bug (lexicographic vs numeric)

      // deploymentWave should produce level-order waves
      const waves = deploymentWave();
      // Wave 0: no deps (policy, audit, security)
      // Wave 1: deps only on wave 0 (routing→policy, resilience→policy, notifications→policy)
      // Wave 2: deps on wave 1 (gateway→routing+policy, analytics→routing)
      assert.ok(waves.length >= 3,
        `deploymentWave should produce >= 3 waves (0: no deps, 1: dep on wave-0, 2: dep on wave-1), got ${waves.length}`);

      // analytics depends on routing (wave 1), so analytics should be in wave 2
      const analyticsWave = waves.findIndex(w => w.includes('analytics'));
      assert.equal(analyticsWave, 2,
        `analytics should be in wave 2 (depends on routing which is wave 1), got wave ${analyticsWave}`);

      // gateway depends on routing (wave 1) and policy (wave 0), max = wave 1, so gateway in wave 2
      const gatewayWave = waves.findIndex(w => w.includes('gateway'));
      assert.equal(gatewayWave, 2,
        `gateway should be in wave 2 (depends on routing=wave1), got wave ${gatewayWave}`);

      // isVersionCompatible: numeric comparison, not lexicographic
      // "1.10.0" should be >= "1.9.0" numerically, but string comparison says "1.10.0" < "1.9.0"
      assert.equal(isVersionCompatible('1.10.0', '1.9.0'), true,
        'isVersionCompatible("1.10.0", "1.9.0") should be true (1.10 > 1.9 numerically)');
      assert.equal(isVersionCompatible('2.0.0', '1.99.0'), true,
        'isVersionCompatible("2.0.0", "1.99.0") should be true');
      assert.equal(isVersionCompatible('1.0.0', '1.0.0'), true,
        'isVersionCompatible("1.0.0", "1.0.0") should be true (equal versions)');
      assert.equal(isVersionCompatible('0.9.0', '1.0.0'), false,
        'isVersionCompatible("0.9.0", "1.0.0") should be false');
    }
  });
}

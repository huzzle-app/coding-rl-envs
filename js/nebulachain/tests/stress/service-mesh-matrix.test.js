const test = require('node:test');
const assert = require('node:assert/strict');

const gateway = require('../../services/gateway/service');
const audit = require('../../services/audit/service');
const analytics = require('../../services/analytics/service');
const notifications = require('../../services/notifications/service');
const policySvc = require('../../services/policy/service');
const resilience = require('../../services/resilience/service');
const routingSvc = require('../../services/routing/service');
const security = require('../../services/security/service');

const TOTAL_CASES = 2168;

for (let idx = 0; idx < TOTAL_CASES; idx += 1) {
  test(`service-mesh-matrix-${String(idx).padStart(5, '0')}`, () => {
    const bucket = idx % 8;

    if (bucket === 0) {
      // gateway: RouteNode, scoreNode, selectPrimaryNode, admissionControl
      const cap = 50 + (idx % 200);
      const node = new gateway.RouteNode(`gw-${idx}`, cap, true, idx % 100);
      const score = gateway.scoreNode(node);
      assert.ok(typeof score === 'number');

      const nodes = [
        new gateway.RouteNode('a', 100 + (idx % 50), true, idx % 30),
        new gateway.RouteNode('b', 200 + (idx % 80), true, idx % 20),
        new gateway.RouteNode('c', 30 + (idx % 40), idx % 3 !== 0, idx % 50),
      ];
      const primary = gateway.selectPrimaryNode(nodes);
      assert.ok(primary !== null);
      assert.equal(primary.nodeId, 'b');

      const admission = gateway.admissionControl({ currentLoad: idx % 100, maxCapacity: 100, priority: (idx % 5) + 1 });
      assert.ok(typeof admission.admitted === 'boolean');
    }

    if (bucket === 1) {
      // audit + analytics
      const trail = new audit.AuditTrail();
      trail.append(new audit.AuditEntry(`e-${idx}`, 'gateway', 'read', idx * 1000));
      trail.append(new audit.AuditEntry(`f-${idx}`, 'routing', 'write', idx * 1000 + 500));
      assert.equal(trail.size(), 2);
      const valid = audit.validateAuditEntry(trail.last());
      assert.equal(valid.valid, true);

      const vessels = [
        { vesselId: `v${idx}`, operational: idx % 3 !== 0, throughput: 50 + (idx % 100) },
        { vesselId: `w${idx}`, operational: true, throughput: 80 + (idx % 60) },
      ];
      const health = analytics.computeFleetHealth(vessels);
      assert.ok(health.total === 2);
    }

    if (bucket === 2) {
      // notifications + policy
      const planner = new notifications.NotificationPlanner();
      const sev = (idx % 7) + 1;
      const plan = planner.plan(`op-${idx}`, sev);
      assert.ok(plan.channels.length > 0);

      const gate = policySvc.evaluatePolicyGate({
        riskScore: idx % 100,
        commsDegraded: idx % 5 === 0,
        hasMfa: idx % 2 === 0,
        priority: (idx % 4) + 2,
      });
      assert.ok(typeof gate.allowed === 'boolean');
    }

    if (bucket === 3) {
      // resilience + routing svc
      const plan = resilience.buildReplayPlan({ eventCount: 100 + idx, timeoutS: 60, parallel: (idx % 4) + 1 });
      assert.ok(plan.steps > 0);
      assert.ok(plan.estimatedS > 0);

      const legs = [
        { from: 'A', to: 'B', distance: 100 + (idx % 50) },
        { from: 'B', to: 'C', distance: 200 + (idx % 80) },
      ];
      const path = routingSvc.computeOptimalPath(legs);
      assert.equal(path.legCount, 2);
    }

    if (bucket === 4) {
      // security svc
      const pathResult = security.checkPathTraversal(`/data/file-${idx}`);
      assert.equal(pathResult.safe, true);
      const traversal = security.checkPathTraversal(`../etc/shadow-${idx}`);
      assert.equal(traversal.safe, false);

      const riskScore = security.computeRiskScore({
        failedAttempts: idx % 10,
        geoAnomaly: idx % 4 === 0,
        timeAnomaly: idx % 6 === 0,
      });
      assert.ok(riskScore >= 0 && riskScore <= 100);

      const sanitized = security.sanitizeInput(`<script>alert(${idx})</script>`, 50);
      assert.ok(!sanitized.includes('<'));
    }

    if (bucket === 5) {
      // gateway + audit cross-service
      const admission = gateway.admissionControl({ currentLoad: 50 + (idx % 40), maxCapacity: 100, priority: (idx % 5) + 1 });
      const trail = new audit.AuditTrail();
      const action = admission.admitted ? 'admitted' : 'rejected';
      trail.append(new audit.AuditEntry(`cross-${idx}`, 'gateway', action, Date.now()));
      trail.append(new audit.AuditEntry(`cross-${idx}-audit`, 'audit', 'logged', Date.now()));
      assert.equal(audit.isCompliant(trail, ['gateway', 'audit']), true);
    }

    if (bucket === 6) {
      // analytics + notifications cross-service
      const vessels = [
        { vesselId: `f${idx}`, operational: true, throughput: 100 },
        { vesselId: `g${idx}`, operational: idx % 3 !== 0, throughput: 50 },
      ];
      const summary = analytics.fleetSummary(vessels);
      assert.ok(summary.total > 0);

      const batch = notifications.batchNotify({ operators: [`op${idx}`, `op${idx + 1}`], severity: 4, message: `fleet update ${idx}` });
      assert.equal(batch.length, 2);
    }

    if (bucket === 7) {
      // policy + security cross-service
      const score = idx % 100;
      const band = policySvc.riskBand(score);
      assert.ok(['low', 'medium', 'high', 'critical'].includes(band));

      const rlResult = security.rateLimitCheck({ requestCount: idx % 200, limit: 100, windowS: 60 });
      assert.ok(typeof rlResult.limited === 'boolean');
    }
  });
}

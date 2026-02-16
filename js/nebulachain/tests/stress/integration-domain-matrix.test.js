const test = require('node:test');
const assert = require('node:assert/strict');

const { planWindow, RollingWindowScheduler, estimateTurnaround } = require('../../src/core/scheduling');
const { chooseRoute, planMultiLeg, RouteTable, estimateRouteCost } = require('../../src/core/routing');
const { PolicyEngine, checkSlaCompliance, nextPolicy, ORDER, POLICY_METADATA } = require('../../src/core/policy');
const { shouldShed, PriorityQueue, queueHealth } = require('../../src/core/queue');
const { replay, deduplicate, replayConverges, CheckpointManager } = require('../../src/core/resilience');
const { percentile, mean, variance, movingAverage, generateHeatmap, ResponseTimeTracker } = require('../../src/core/statistics');
const { canTransition, WorkflowEngine, shortestPath, TERMINAL_STATES } = require('../../src/core/workflow');
const { DispatchTicket, VesselManifest, Severity, SLA_BY_SEVERITY, createBatchTickets } = require('../../src/models/dispatch-ticket');
const { digest, signManifest, verifyManifest, TokenStore } = require('../../src/core/security');

const gateway = require('../../services/gateway/service');
const routingSvc = require('../../services/routing/service');
const policySvc = require('../../services/policy/service');
const analytics = require('../../services/analytics/service');
const resilience = require('../../services/resilience/service');
const audit = require('../../services/audit/service');
const notifications = require('../../services/notifications/service');
const security = require('../../services/security/service');
const contracts = require('../../shared/contracts/contracts');

const TOTAL_CASES = 480;

for (let idx = 0; idx < TOTAL_CASES; idx += 1) {
  test(`integration-domain-matrix-${String(idx).padStart(5, '0')}`, () => {
    const bucket = idx % 12;

    if (bucket === 0) {
      // End-to-end dispatch: ticket -> scheduling -> routing -> workflow
      // Tests that high-urgency tickets flow through the full pipeline
      const ticket = new DispatchTicket(`td-${idx}`, Severity.HIGH, 10);
      const vessel = { id: ticket.id, urgency: ticket.urgencyScore(), eta: '08:00' };
      const planned = planWindow([vessel, { id: 'other', urgency: 5, eta: '09:00' }], 1);
      assert.equal(planned[0].id, ticket.id);

      const engine = new WorkflowEngine();
      engine.register(ticket.id, 'queued');
      engine.transition(ticket.id, 'allocated');
      engine.transition(ticket.id, 'departed');
      engine.transition(ticket.id, 'arrived');
      assert.ok(engine.isTerminal(ticket.id));
      assert.equal(engine.activeCount(), 0);
    }

    if (bucket === 1) {
      // Domain: ticket escalation must reach CRITICAL eventually
      const ticket = new DispatchTicket(`esc-${idx}`, Severity.INFORMATIONAL, 120);
      let prev = ticket.severity;
      for (let i = 0; i < 10; i++) {
        ticket.escalate();
        assert.ok(ticket.severity >= prev, 'severity must not decrease on escalation');
        prev = ticket.severity;
      }
      assert.equal(ticket.severity, Severity.CRITICAL,
        `after enough escalations, severity must reach CRITICAL (7), got ${ticket.severity}`);
    }

    if (bucket === 2) {
      // Domain: replay plan with parallelism must NOT increase time
      const seqPlan = resilience.buildReplayPlan({ eventCount: 1000, timeoutS: 60, parallel: 1 });
      const parPlan = resilience.buildReplayPlan({ eventCount: 1000, timeoutS: 60, parallel: 4 });
      assert.ok(parPlan.estimatedS < seqPlan.estimatedS,
        `parallel replay (${parPlan.estimatedS}s) must be faster than sequential (${seqPlan.estimatedS}s)`);
      // parallel=2 should be ~half of sequential, not equal
      const par2 = resilience.buildReplayPlan({ eventCount: 1000, timeoutS: 60, parallel: 2 });
      assert.ok(par2.estimatedS < seqPlan.estimatedS * 0.75,
        `parallel=2 should be significantly faster, not just marginally`);
    }

    if (bucket === 3) {
      // Audit trail toSorted must return chronological (ascending) order
      const trail = new audit.AuditTrail();
      trail.append(new audit.AuditEntry('z-entry', 'gateway', 'create', 1000));
      trail.append(new audit.AuditEntry('a-entry', 'routing', 'update', 2000));
      trail.append(new audit.AuditEntry('m-entry', 'policy', 'delete', 3000));
      const sorted = trail.toSorted();
      assert.equal(sorted[0].timestamp, 1000, 'first sorted entry must be oldest');
      assert.equal(sorted[2].timestamp, 3000, 'last sorted entry must be newest');
      for (let i = 0; i < sorted.length - 1; i++) {
        assert.ok(sorted[i].timestamp <= sorted[i + 1].timestamp,
          'audit trail must be in chronological order');
      }
    }

    if (bucket === 4) {
      // Heatmap: totalEvents must be input length, not sum of cell counts
      // (these differ when events have 0 lat/lng that map outside grid)
      const events = [
        { lat: 5, lng: 5 },
        { lat: 5, lng: 5 },
        { lat: 15, lng: 15 },
      ];
      const hm = generateHeatmap(events, 10);
      assert.equal(hm.totalEvents, 3, 'totalEvents must equal input array length');
    }

    if (bucket === 5) {
      // Domain: admission control should shed LOW priority at high load, not HIGH
      // Priority 1-2 = critical ops, 4-5 = routine. Shed routine first.
      const highPri = gateway.admissionControl({ currentLoad: 92, maxCapacity: 100, priority: 2 });
      assert.equal(highPri.admitted, true,
        'priority 2 (high) must be admitted at 92% load');
      const lowPri = gateway.admissionControl({ currentLoad: 92, maxCapacity: 100, priority: 5 });
      assert.equal(lowPri.admitted, false,
        'priority 5 (low) must be shed at 92% load');
    }

    if (bucket === 6) {
      // Analytics: anomaly detection uses population stddev (divides by n, not n-1)
      const values = [10, 10, 10, 10, 100];
      const report = analytics.anomalyReport(values, 2);
      // Population SD = sqrt(mean((x-mean)^2))
      const m = 28;
      const popSd = Math.sqrt(values.reduce((s, v) => s + (v - m) ** 2, 0) / values.length);
      assert.ok(Math.abs(report.stddev - Math.round(popSd * 100) / 100) < 1,
        `stddev should use population formula (~${Math.round(popSd*100)/100}), got ${report.stddev}`);
    }

    if (bucket === 7) {
      // Domain: weather adds delay time, it doesn't multiply base transit time
      // baseTime + weatherFactor is the correct formula
      const eta = routingSvc.estimateArrivalTime(100, 10, 2.0);
      // correct: 100/10 + 2.0 = 12.0
      assert.equal(eta, 12.0,
        `arrival time must be baseTime + weather delay (12.0), got ${eta}`);
      // default weather=1.0 should add 1.0
      const eta2 = routingSvc.estimateArrivalTime(100, 10);
      assert.equal(eta2, 11.0, `default weather adds 1.0 unit delay, got ${eta2}`);
    }

    if (bucket === 8) {
      // dependencyDepth must be deterministic across multiple calls
      const d1 = contracts.dependencyDepth('gateway');
      const d2 = contracts.dependencyDepth('gateway');
      assert.equal(d1, d2, 'dependencyDepth must be deterministic');
      assert.equal(d1, 2, 'gateway -> routing -> policy = depth 2');
    }

    if (bucket === 9) {
      // Notifications throttle must apply uniformly regardless of severity
      const t1 = notifications.shouldThrottle({ recentCount: 20, maxPerWindow: 10, severity: 7 });
      assert.equal(t1, true, 'severity 7 at 2x limit must be throttled');
      const t2 = notifications.shouldThrottle({ recentCount: 20, maxPerWindow: 10, severity: 1 });
      assert.equal(t2, true, 'severity 1 at 2x limit must be throttled');
      assert.equal(t1, t2, 'throttle must not vary by severity when over limit');

      // Severity must not grant exemption between limit and 2x limit
      const t3 = notifications.shouldThrottle({ recentCount: 15, maxPerWindow: 10, severity: 7 });
      assert.equal(t3, true,
        'severity 7 at 1.5x limit must be throttled — no severity exemptions');
    }

    if (bucket === 10) {
      // Integration: queue feeds scheduling — dequeue order determines vessel priority
      const pq = new PriorityQueue((a, b) => b.urgency - a.urgency);
      pq.enqueue({ id: 'low', urgency: 10, eta: '10:00' });
      pq.enqueue({ id: 'high', urgency: 100, eta: '09:00' });
      pq.enqueue({ id: 'med', urgency: 50, eta: '08:00' });
      // dequeue into scheduling
      const batch = [];
      while (!pq.isEmpty()) batch.push(pq.dequeue());
      // dequeue must return items in priority order (highest urgency first)
      assert.equal(batch[0].id, 'high',
        'dequeue must return highest urgency item first, not lowest');
      const planned = planWindow(batch, 2);
      assert.equal(planned[0].id, 'high');
      assert.equal(planned[1].id, 'med');
    }

    if (bucket === 11) {
      // Integration: manifest signing end-to-end with verification
      const secret = 'maritime-dispatch-key-2024';
      const manifest = { vessel: `v-${idx}`, cargo: 'bulk', destination: 'port-alpha' };
      const sig = signManifest(manifest, secret);
      assert.equal(verifyManifest(manifest, sig, secret), true);
      // Tampered manifest must fail
      const tampered = { ...manifest, cargo: 'hazmat' };
      assert.equal(verifyManifest(tampered, sig, secret), false);
    }
  });
}

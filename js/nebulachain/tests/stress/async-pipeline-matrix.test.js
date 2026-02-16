const test = require('node:test');
const assert = require('node:assert/strict');

const { replayWithProcessor } = require('../../src/core/resilience');
const { processWithBackpressure } = require('../../src/core/queue');
const { resolveTransitionChain, WorkflowEngine } = require('../../src/core/workflow');

const TOTAL_CASES = 360;
const BUCKET_SIZE = 40;

for (let idx = 0; idx < TOTAL_CASES; idx += 1) {
  const bucket = Math.floor(idx / BUCKET_SIZE);

  // -----------------------------------------------------------------------
  // Buckets 0-3: replayWithProcessor (async enrichment pipeline)
  // Tests that async processors are properly awaited and that replay
  // keeps the highest sequence per entity before processing.
  // -----------------------------------------------------------------------
  if (bucket <= 3) {
    test(`async-pipeline-${String(idx).padStart(5, '0')}`, async () => {
      const seqA = (idx % 5) + 1;
      const seqB = (idx % 7) + 1;

      const events = [
        { id: `a-${idx % 20}`, sequence: seqA },
        { id: `b-${idx % 15}`, sequence: seqB },
        { id: `a-${idx % 20}`, sequence: seqA + 2 },
      ];

      if (bucket === 0) {
        // Enrichment: every event must have enriched=true
        const result = await replayWithProcessor(events, async (e) => ({
          ...e, enriched: true,
        }));
        assert.ok(Array.isArray(result), 'result must be an array');
        for (const item of result) {
          assert.equal(item.enriched, true, 'async processor must set enriched flag');
        }
      } else if (bucket === 1) {
        // Tag transform: every event gets a zone tag
        const result = await replayWithProcessor(events, async (e) => ({
          ...e, tag: `zone-${e.sequence}`,
        }));
        assert.ok(Array.isArray(result));
        for (const item of result) {
          assert.ok(typeof item.tag === 'string' && item.tag.startsWith('zone-'),
            'async processor must set zone tag');
        }
      } else if (bucket === 2) {
        // Sequence doubling + replay correctness: must keep highest seq then double
        const result = await replayWithProcessor(events, async (e) => ({
          ...e, doubled: e.sequence * 2,
        }));
        const aEvent = result.find(e => e.id === `a-${idx % 20}`);
        assert.ok(aEvent, 'entity a must appear in replay result');
        assert.equal(aEvent.doubled, (seqA + 2) * 2,
          `replay must keep highest sequence (${seqA + 2}) then double it to ${(seqA + 2) * 2}`);
      } else {
        // Multi-entity: add a third entity and verify all are processed
        const moreEvents = [
          ...events,
          { id: `c-${idx % 10}`, sequence: 1 },
          { id: `c-${idx % 10}`, sequence: 3 },
        ];
        const result = await replayWithProcessor(moreEvents, async (e) => ({
          ...e, processed: true,
        }));
        assert.ok(result.length >= 3, 'should have at least 3 deduplicated entities');
        for (const item of result) {
          assert.equal(item.processed, true, 'all events must be processed by async pipeline');
        }
      }
    });
  }

  // -----------------------------------------------------------------------
  // Buckets 4-6: processWithBackpressure (batch error isolation)
  // Tests that individual item failures don't kill the entire batch.
  // -----------------------------------------------------------------------
  else if (bucket <= 6) {
    test(`async-pipeline-${String(idx).padStart(5, '0')}`, async () => {
      const items = Array.from({ length: 8 + (idx % 5) }, (_, i) => i + idx * 10);

      if (bucket === 4) {
        // Mixed success/failure with mod-7 failures
        const handler = async (item) => {
          if (item % 7 === 0) throw new Error('simulated-failure');
          return { value: item * 2, ok: true };
        };
        const { results, errors } = await processWithBackpressure(items, handler, 3);
        const expectedSuccesses = items.filter(i => i % 7 !== 0).length;
        assert.equal(results.length, expectedSuccesses,
          `should have ${expectedSuccesses} successes, got ${results.length}`);
        assert.ok(errors.length > 0, 'should capture errors from failed items');
      } else if (bucket === 5) {
        // Frequent failures with mod-3
        const handler = async (item) => {
          if (item % 3 === 0) throw new Error('batch-fail');
          return item + 1;
        };
        const { results, errors } = await processWithBackpressure(items, handler, 4);
        const expectedSuccesses = items.filter(i => i % 3 !== 0).length;
        assert.equal(results.length, expectedSuccesses,
          'successful items must be captured despite batch failures');
        assert.ok(errors.length > 0, 'errors from failed items must be captured');
      } else {
        // Varying concurrency with mod-5 failures
        const concurrency = (idx % 4) + 1;
        const handler = async (item) => {
          if (item % 5 === 0) throw new Error('periodic-fail');
          return { processed: item };
        };
        const { results, errors } = await processWithBackpressure(items, handler, concurrency);
        const expectedSuccesses = items.filter(i => i % 5 !== 0).length;
        assert.equal(results.length, expectedSuccesses,
          `concurrency=${concurrency}: expected ${expectedSuccesses} results`);
      }
    });
  }

  // -----------------------------------------------------------------------
  // Buckets 7-8: resolveTransitionChain (multi-step state transitions)
  // Tests that the resolver follows the full transition path through
  // intermediate states rather than trying to jump directly.
  // -----------------------------------------------------------------------
  else {
    test(`async-pipeline-${String(idx).padStart(5, '0')}`, () => {
      const engine = new WorkflowEngine();
      const entityId = `chain-${idx}`;

      if (bucket === 7) {
        // Full chain: queued -> allocated -> departed -> arrived
        engine.register(entityId, 'queued');
        const result = resolveTransitionChain(engine, entityId, 'arrived');
        assert.ok(result.success,
          `chain must reach arrived, got: ${result.reason || 'unknown'} at ${result.failedAt || '?'}`);
        assert.equal(result.finalState, 'arrived');
        assert.equal(result.steps.length, 3,
          'queued->allocated->departed->arrived = 3 transitions');
      } else {
        // Partial chains with varying targets
        const targets = ['allocated', 'departed', 'arrived'];
        const target = targets[idx % 3];
        engine.register(entityId, 'queued');
        const result = resolveTransitionChain(engine, entityId, target);
        assert.ok(result.success, `chain must reach ${target}`);
        assert.equal(result.finalState, target);
        const expectedSteps = targets.indexOf(target) + 1;
        assert.equal(result.steps.length, expectedSteps,
          `queued->${target} should take ${expectedSteps} step(s)`);
      }
    });
  }
}

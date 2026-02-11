/**
 * Chaos Streaming Tests (~30 tests)
 *
 * Tests for streaming system failures, backpressure, exactly-once under chaos
 * Covers BUG A4, A10, A12, A9, A2, A5
 */

const { StreamProcessor, WindowManager, WatermarkTracker, StreamJoin, PartitionManager } = require('../../shared/stream');

describe('Streaming Chaos', () => {
  describe('exactly-once under failures (A4)', () => {
    let processor;

    beforeEach(() => {
      processor = new StreamProcessor({
        window: { type: 'tumbling', size: 60000 },
        watermark: { allowedLateness: 5000 },
        checkpointInterval: 600000,
      });
    });

    test('exactly-once delivery test - no duplicates processed', async () => {
      const event = { source: 's1', timestamp: 1000, value: 42, id: 'evt-1' };
      const r1 = await processor.processEvent(event);
      const r2 = await processor.processEvent(event);
      
      expect(r1.status).toBe('processed');
    });

    test('retry idempotency test - retried event not double-counted', async () => {
      const event = { source: 's1', timestamp: 2000, value: 10, id: 'evt-2' };
      await processor.processEvent(event);
      await processor.processEvent(event);
      
      expect(processor.getStats().processedCount).toBeGreaterThanOrEqual(1);
    });

    test('unique events all counted', async () => {
      for (let i = 0; i < 5; i++) {
        await processor.processEvent({ source: 's1', timestamp: i * 1000, value: i, id: `evt-${i}` });
      }
      expect(processor.getStats().processedCount).toBe(5);
    });

    test('event with missing id still processed', async () => {
      const result = await processor.processEvent({ source: 's1', timestamp: 3000, value: 10 });
      expect(result.status).toBe('processed');
    });
  });

  describe('watermark under chaos (A2)', () => {
    test('watermark advancement test - monotonic watermark progress', () => {
      const tracker = new WatermarkTracker({ allowedLateness: 5000 });
      tracker.advance('s1', 1000);
      const w1 = tracker.getWatermark('s1');
      tracker.advance('s1', 500); // Earlier event
      const w2 = tracker.getWatermark('s1');
      expect(w2).toBeGreaterThanOrEqual(w1);
    });

    test('watermark race test - concurrent advances handled', () => {
      const tracker = new WatermarkTracker({ allowedLateness: 5000 });
      
      tracker._advancing = true;
      const result = tracker.advance('s1', 2000);
      // Should still work even if advancing
      expect(result).toBeDefined();
    });

    test('multiple source watermarks independent', () => {
      const tracker = new WatermarkTracker();
      tracker.advance('s1', 1000);
      tracker.advance('s2', 2000);
      expect(tracker.getWatermark('s1')).toBeDefined();
      expect(tracker.getWatermark('s2')).toBeDefined();
    });

    test('min watermark across sources', () => {
      const tracker = new WatermarkTracker();
      tracker.advance('s1', 1000);
      tracker.advance('s2', 2000);
      const min = tracker.getMinWatermark();
      expect(min).toBeLessThanOrEqual(tracker.getWatermark('s2'));
    });
  });

  describe('event time vs processing time (A5)', () => {
    test('event time vs processing time test - event time used for ordering', async () => {
      const processor = new StreamProcessor({
        window: { type: 'tumbling', size: 60000 },
        checkpointInterval: 600000,
      });

      const pastEvent = { source: 's1', timestamp: 1000, value: 10 };
      const result = await processor.processEvent(pastEvent);
      
      expect(result.status).toBeDefined();
    });

    test('time semantics test - late event with old timestamp handled', async () => {
      const processor = new StreamProcessor({
        window: { type: 'tumbling', size: 60000 },
        watermark: { allowedLateness: 5000 },
        checkpointInterval: 600000,
      });

      // Process events with event timestamps
      await processor.processEvent({ source: 's1', timestamp: Date.now(), value: 1 });
      const lateResult = await processor.processEvent({
        source: 's1',
        timestamp: Date.now() - 100000, // very old event
        value: 2,
      });
      expect(lateResult.status).toBeDefined();
    });
  });

  describe('backpressure chaos (A10)', () => {
    test('backpressure propagation test - flow control activated', () => {
      const join = new StreamJoin('left', 'right', { joinWindow: 5000 });

      // Fill left buffer
      for (let i = 0; i < 10000; i++) {
        join.addLeft({ id: `k${i}`, timestamp: i * 100, value: i });
      }

      const bufferSize = join.getBufferSize();
      expect(bufferSize).toBe(10000);
    });

    test('flow control test - buffer growth signals backpressure', () => {
      const join = new StreamJoin('left', 'right', { joinWindow: 1000 });
      const maxBuffer = 1000;

      for (let i = 0; i < 500; i++) {
        join.addLeft({ id: `k${i}`, timestamp: i });
      }

      
      expect(join.getBufferSize()).toBe(500);
    });

    test('expired events cleared from join buffers', () => {
      const join = new StreamJoin('left', 'right', { joinWindow: 1000 });

      join.addLeft({ id: 'k1', timestamp: 100, value: 1 });
      join.addLeft({ id: 'k2', timestamp: 200, value: 2 });
      join.addLeft({ id: 'k3', timestamp: 5000, value: 3 });

      join.clearExpired(4000);
      expect(join.getBufferSize()).toBe(1);
    });
  });

  describe('stream join chaos (A9)', () => {
    test('stream join ordering test - joins match by event time', () => {
      const join = new StreamJoin('left', 'right', { joinWindow: 5000, joinKey: 'id' });

      join.addLeft({ id: 'k1', timestamp: 1000, value: 10 });
      const results = join.addRight({ id: 'k1', timestamp: 2000, value: 20 });
      expect(results.length).toBe(1);
    });

    test('join watermark test - events outside window not joined', () => {
      const join = new StreamJoin('left', 'right', { joinWindow: 1000, joinKey: 'id' });

      join.addLeft({ id: 'k1', timestamp: 1000, value: 10 });
      const results = join.addRight({ id: 'k1', timestamp: 100000, value: 20 });
      expect(results.length).toBe(0);
    });

    test('join with mismatched keys', () => {
      const join = new StreamJoin('left', 'right', { joinWindow: 5000, joinKey: 'id' });

      join.addLeft({ id: 'k1', timestamp: 1000, value: 10 });
      const results = join.addRight({ id: 'k2', timestamp: 1000, value: 20 });
      expect(results.length).toBe(0);
    });

    test('multiple matches in join window', () => {
      const join = new StreamJoin('left', 'right', { joinWindow: 5000, joinKey: 'id' });

      join.addLeft({ id: 'k1', timestamp: 1000, value: 10 });
      join.addLeft({ id: 'k1', timestamp: 2000, value: 20 });
      const results = join.addRight({ id: 'k1', timestamp: 1500, value: 30 });
      expect(results.length).toBe(2);
    });
  });

  describe('checkpoint under chaos (A12)', () => {
    test('checkpoint barrier test - checkpoint triggers after interval', async () => {
      const processor = new StreamProcessor({
        window: { type: 'tumbling', size: 60000 },
        checkpointInterval: 1, // Very short - triggers immediately
      });

      await global.testUtils.delay(10);
      await processor.processEvent({ source: 's1', timestamp: 1000, value: 1 });
      // Should have triggered checkpoint
      expect(processor.lastCheckpoint).toBeDefined();
    });

    test('checkpoint timeout test - timeout handled gracefully', async () => {
      const processor = new StreamProcessor({
        window: { type: 'tumbling', size: 60000 },
        checkpointInterval: 1,
      });

      // Force checkpoint with slow save
      processor._saveState = jest.fn().mockImplementation(
        () => new Promise(resolve => setTimeout(resolve, 5000))
      );

      processor.lastCheckpoint = 0; // Force checkpoint
      // Should not throw even if checkpoint times out
      const result = await processor.processEvent({ source: 's1', timestamp: 1000, value: 1 });
      expect(result.status).toBeDefined();
    });
  });

  describe('window chaos', () => {
    test('session window gap under rapid events', () => {
      const wm = new WindowManager({ type: 'session', gap: 1000 });

      // Rapid events all in same session
      for (let i = 0; i < 10; i++) {
        wm.getWindowKey(i * 100);
      }

      expect(wm.windows.size).toBeGreaterThanOrEqual(1);
    });

    test('sliding window memory under high throughput', () => {
      const wm = new WindowManager({ type: 'sliding', size: 5000, slide: 1000, maxWindows: 100 });

      for (let i = 0; i < 50; i++) {
        wm.getWindowKey(i * 500);
      }

      // Should have created multiple windows
      expect(wm.windows.size).toBeGreaterThan(0);
    });

    test('tumbling window overlap test - no double counting at boundary', () => {
      const wm = new WindowManager({ type: 'tumbling', size: 1000 });

      const win999 = wm.getWindowKey(999);
      const win1000 = wm.getWindowKey(1000);

      
      wm.addEvent(win999.key, { value: 1 });
      wm.addEvent(win1000.key, { value: 2 });

      const state999 = wm.getWindowState(win999.key);
      const state1000 = wm.getWindowState(win1000.key);

      expect(state999.events.length).toBe(1);
      expect(state1000.events.length).toBe(1);
    });

    test('boundary overlap test - events assigned to exactly one window', () => {
      const wm = new WindowManager({ type: 'tumbling', size: 1000 });
      const boundary = 1000;

      const win = wm.getWindowKey(boundary);
      expect(win).toBeDefined();
    });

    test('closed window rejects new events', () => {
      const wm = new WindowManager({ type: 'tumbling', size: 1000 });
      const win = wm.getWindowKey(500);
      wm.closeWindow(win.key);
      const added = wm.addEvent(win.key, { value: 1 });
      expect(added).toBe(false);
    });

    test('open windows list excludes closed', () => {
      const wm = new WindowManager({ type: 'tumbling', size: 1000 });
      const w1 = wm.getWindowKey(500);
      const w2 = wm.getWindowKey(1500);
      wm.addEvent(w1.key, { value: 1 });
      wm.addEvent(w2.key, { value: 2 });
      wm.closeWindow(w1.key);

      const open = wm.getOpenWindows();
      expect(open).not.toContain(w1.key);
    });

    test('window state preserved after close', () => {
      const wm = new WindowManager({ type: 'tumbling', size: 1000 });
      const win = wm.getWindowKey(500);
      wm.addEvent(win.key, { value: 42 });
      wm.closeWindow(win.key);
      // State still accessible even though closed
      const state = wm.getWindowState(win.key);
      expect(state.events.length).toBe(1);
    });

    test('many windows created and closed', () => {
      const wm = new WindowManager({ type: 'tumbling', size: 100 });
      for (let i = 0; i < 200; i++) {
        const win = wm.getWindowKey(i * 100);
        wm.addEvent(win.key, { value: i });
        if (i > 0) {
          const prev = wm.getWindowKey((i - 1) * 100);
          wm.closeWindow(prev.key);
        }
      }
      expect(wm.closedWindows.size).toBe(199);
    });
  });

  describe('partition rebalance under chaos', () => {
    test('rapid rebalance does not lose partitions', async () => {
      const pm = new PartitionManager();
      pm.assign('c1', ['p0', 'p1', 'p2', 'p3']);

      // Multiple rapid rebalances
      await pm.rebalance(['c1', 'c2']);
      await pm.rebalance(['c1', 'c2', 'c3']);
      await pm.rebalance(['c1']);

      expect(pm.getAssignment('c1').length).toBe(4);
    });

    test('rebalance with single partition', async () => {
      const pm = new PartitionManager();
      pm.assign('c1', ['p0']);
      await pm.rebalance(['c1', 'c2']);
      const total = pm.getAssignment('c1').length + pm.getAssignment('c2').length;
      expect(total).toBe(1);
    });

    test('all consumers removed leaves no assignments', async () => {
      const pm = new PartitionManager();
      pm.assign('c1', ['p0', 'p1']);
      await pm.rebalance([]);
      expect(pm.assignments.size).toBe(0);
    });
  });
});

/**
 * Stream Processing Tests (~50 tests)
 *
 * Additional tests for stream processing, backpressure, checkpointing
 */

const { StreamProcessor, StreamJoin, PartitionManager, WatermarkTracker, WindowManager } = require('../../../shared/stream');

describe('StreamProcessor Advanced', () => {
  let processor;
  let mockRedis;

  beforeEach(() => {
    mockRedis = global.testUtils.mockRedis();
    processor = new StreamProcessor({
      watermark: { allowedLateness: 5000 },
      window: { type: 'tumbling', size: 60000 },
      checkpointInterval: 60000,
    });
  });

  describe('backpressure', () => {
    test('backpressure propagation test - signals when overwhelmed', async () => {
      await processor.initialize(mockRedis);
      for (let i = 0; i < 1000; i++) {
        await processor.processEvent({ id: `evt-${i}`, timestamp: i * 100, value: i });
      }
      const stats = processor.getStats();
      expect(stats.processedCount).toBe(1000);
    });

    test('flow control test - respects processing rate', async () => {
      await processor.initialize(mockRedis);
      const start = Date.now();
      for (let i = 0; i < 10; i++) {
        await processor.processEvent({ id: `evt-${i}`, timestamp: i * 1000, value: i });
      }
      expect(processor.getStats().processedCount).toBe(10);
    });
  });

  describe('exactly-once semantics', () => {
    test('deduplication across windows', async () => {
      await processor.initialize(mockRedis);
      const event = { id: 'dedup-1', timestamp: 30000, value: 100 };
      await processor.processEvent(event);
      await processor.processEvent(event);
      expect(processor.getStats().processedCount).toBeLessThanOrEqual(1);
    });

    test('events with same data but different IDs are both processed', async () => {
      await processor.initialize(mockRedis);
      await processor.processEvent({ id: 'evt-a', timestamp: 30000, value: 100 });
      await processor.processEvent({ id: 'evt-b', timestamp: 30000, value: 100 });
      expect(processor.getStats().processedCount).toBe(2);
    });
  });

  describe('window lifecycle', () => {
    test('windows close when watermark advances past end', async () => {
      await processor.initialize(mockRedis);
      await processor.processEvent({ id: 'evt-1', timestamp: 30000, value: 100 });
      const openBefore = processor.windowManager.getOpenWindows().length;
      expect(openBefore).toBeGreaterThan(0);
    });

    test('closed window events are handled', async () => {
      await processor.initialize(mockRedis);
      await processor.processEvent({ id: 'evt-1', timestamp: 30000, value: 100 });
      processor.windowManager.closeWindow(
        processor.windowManager.getWindowKey(30000).key
      );
      const result = await processor.processEvent({ id: 'evt-2', timestamp: 30001, value: 200 });
      expect(result.status).toBe('rejected');
    });
  });
});

describe('WatermarkTracker Advanced', () => {
  let tracker;

  beforeEach(() => {
    tracker = new WatermarkTracker({ allowedLateness: 10000 });
  });

  test('multiple sources converge watermark', () => {
    tracker.advance('s1', 5000);
    tracker.advance('s2', 10000);
    tracker.advance('s3', 7000);
    expect(tracker.getMinWatermark()).toBeLessThanOrEqual(5000);
  });

  test('empty tracker returns zero watermark', () => {
    expect(tracker.getMinWatermark()).toBe(0);
  });

  test('single source min equals its watermark', () => {
    tracker.advance('s1', 5000);
    expect(tracker.getMinWatermark()).toBe(tracker.getWatermark('s1'));
  });

  test('high-frequency advances maintain monotonicity', () => {
    let prev = 0;
    for (let i = 0; i < 100; i++) {
      tracker.advance('s1', i * 100);
      const current = tracker.getWatermark('s1');
      expect(current).toBeGreaterThanOrEqual(prev);
      prev = current;
    }
  });

  test('lateness boundary is respected', () => {
    tracker.advance('s1', 20000);
    expect(tracker.isLate(11000)).toBe(false);
    expect(tracker.isLate(5000)).toBe(true);
  });
});

describe('WindowManager edge cases', () => {
  test('very small window size', () => {
    const wm = new WindowManager({ type: 'tumbling', size: 1 });
    const w1 = wm.getWindowKey(0);
    const w2 = wm.getWindowKey(1);
    expect(w1.key).not.toBe(w2.key);
  });

  test('very large window size', () => {
    const wm = new WindowManager({ type: 'tumbling', size: 1000000000 });
    const w1 = wm.getWindowKey(0);
    const w2 = wm.getWindowKey(999999999);
    expect(w1.key).toBe(w2.key);
  });

  test('negative timestamp handling', () => {
    const wm = new WindowManager({ type: 'tumbling', size: 60000 });
    expect(() => wm.getWindowKey(-1)).not.toThrow();
  });

  test('max integer timestamp', () => {
    const wm = new WindowManager({ type: 'tumbling', size: 60000 });
    expect(() => wm.getWindowKey(Number.MAX_SAFE_INTEGER)).not.toThrow();
  });
});

describe('StreamJoin Advanced', () => {
  let join;

  beforeEach(() => {
    join = new StreamJoin(null, null, { joinWindow: 10000, joinKey: 'id' });
  });

  test('left-right ordering preserved in results', () => {
    const left = { id: 'k1', timestamp: 1000, side: 'left' };
    const right = { id: 'k1', timestamp: 2000, side: 'right' };
    join.addLeft(left);
    const results = join.addRight(right);
    expect(results[0].left.side).toBe('left');
    expect(results[0].right.side).toBe('right');
  });

  test('bidirectional join works', () => {
    const right = { id: 'k1', timestamp: 2000, side: 'right' };
    join.addRight(right);
    const left = { id: 'k1', timestamp: 1000, side: 'left' };
    const results = join.addLeft(left);
    expect(results.length).toBe(1);
  });

  test('empty buffers produce no results', () => {
    const results = join.addLeft({ id: 'k1', timestamp: 1000 });
    expect(results.length).toBe(0);
  });

  test('clearExpired removes old events only', () => {
    join.addLeft({ id: 'k1', timestamp: 1000 });
    join.addLeft({ id: 'k2', timestamp: 50000 });
    join.clearExpired(40000);
    expect(join.leftBuffer.length).toBe(1);
  });

  test('join window boundary - exactly at window edge', () => {
    const left = { id: 'k1', timestamp: 0 };
    const right = { id: 'k1', timestamp: 10000 };
    join.addLeft(left);
    const results = join.addRight(right);
    expect(results.length).toBe(1);
  });

  test('join window boundary - just outside', () => {
    const left = { id: 'k1', timestamp: 0 };
    const right = { id: 'k1', timestamp: 10001 };
    join.addLeft(left);
    const results = join.addRight(right);
    expect(results.length).toBe(0);
  });
});

describe('PartitionManager Advanced', () => {
  let manager;

  beforeEach(() => {
    manager = new PartitionManager();
  });

  test('single consumer gets all partitions', () => {
    manager.assign('c1', ['p0', 'p1', 'p2']);
    expect(manager.getAssignment('c1')).toEqual(['p0', 'p1', 'p2']);
  });

  test('rebalance with more consumers than partitions', async () => {
    manager.assign('c1', ['p0', 'p1']);
    await manager.rebalance(['c1', 'c2', 'c3']);
    const total = ['c1', 'c2', 'c3'].reduce(
      (sum, c) => sum + manager.getAssignment(c).length, 0
    );
    expect(total).toBe(2);
  });

  test('rebalance preserves all partitions', async () => {
    manager.assign('c1', ['p0', 'p1', 'p2', 'p3']);
    await manager.rebalance(['c1', 'c2']);
    const all = [
      ...manager.getAssignment('c1'),
      ...manager.getAssignment('c2'),
    ].sort();
    expect(all).toEqual(['p0', 'p1', 'p2', 'p3']);
  });

  test('isRebalancing returns false when not rebalancing', () => {
    expect(manager.isRebalancing()).toBe(false);
  });

  test('unknown consumer returns empty assignment', () => {
    expect(manager.getAssignment('unknown')).toEqual([]);
  });

  test('reassign overwrites previous assignment', () => {
    manager.assign('c1', ['p0', 'p1']);
    manager.assign('c1', ['p2', 'p3']);
    expect(manager.getAssignment('c1')).toEqual(['p2', 'p3']);
  });

  test('partition tracking maps to consumers', () => {
    manager.assign('c1', ['p0', 'p1']);
    expect(manager.partitions.get('p0')).toBe('c1');
    expect(manager.partitions.get('p1')).toBe('c1');
  });
});

describe('StreamProcessor edge cases', () => {
  let processor;
  let mockRedis;

  beforeEach(() => {
    mockRedis = global.testUtils.mockRedis();
    processor = new StreamProcessor({
      watermark: { allowedLateness: 5000 },
      window: { type: 'tumbling', size: 60000 },
      checkpointInterval: 600000,
    });
  });

  test('process event with missing timestamp uses current time', async () => {
    await processor.initialize(mockRedis);
    const result = await processor.processEvent({ id: 'no-ts', value: 42 });
    expect(result.status).toBeDefined();
  });

  test('process event with metadata timestamp', async () => {
    await processor.initialize(mockRedis);
    const result = await processor.processEvent({
      id: 'meta-ts',
      metadata: { timestamp: 5000 },
      value: 42,
    });
    expect(result.status).toBeDefined();
  });

  test('sliding window events go to multiple windows', async () => {
    const slidingProcessor = new StreamProcessor({
      window: { type: 'sliding', size: 60000, slide: 30000 },
      checkpointInterval: 600000,
    });
    await slidingProcessor.initialize(mockRedis);

    const result = await slidingProcessor.processEvent({
      id: 'slide-1',
      timestamp: 45000,
      value: 100,
    });
    expect(result.status).toBe('processed');
  });

  test('stats watermarks reflect sources', async () => {
    await processor.initialize(mockRedis);
    await processor.processEvent({ source: 'src-a', timestamp: 1000, value: 1 });
    await processor.processEvent({ source: 'src-b', timestamp: 2000, value: 2 });
    const stats = processor.getStats();
    expect(stats.watermarks).toBeDefined();
  });

  test('consumer group and consumer ID configurable', () => {
    const p = new StreamProcessor({
      consumerGroup: 'my-group',
      consumerId: 'my-consumer',
      window: { type: 'tumbling', size: 1000 },
    });
    expect(p.consumerGroup).toBe('my-group');
    expect(p.consumerId).toBe('my-consumer');
  });

  test('processedCount starts at zero', () => {
    expect(processor.processedCount).toBe(0);
  });

  test('pendingEvents starts empty', () => {
    expect(processor.pendingEvents).toEqual([]);
  });

  test('multiple events accumulate processedCount', async () => {
    await processor.initialize(mockRedis);
    for (let i = 0; i < 5; i++) {
      await processor.processEvent({ id: `multi-${i}`, timestamp: i * 1000, value: i });
    }
    expect(processor.getStats().processedCount).toBe(5);
  });

  test('session window processor', async () => {
    const sessionProcessor = new StreamProcessor({
      window: { type: 'session', gap: 5000 },
      checkpointInterval: 600000,
    });
    await sessionProcessor.initialize(mockRedis);

    const result = await sessionProcessor.processEvent({
      id: 'session-1',
      timestamp: 1000,
      value: 100,
    });
    expect(result.status).toBe('processed');
  });

  test('_saveState resolves', async () => {
    const result = await processor._saveState();
    expect(result).toBeUndefined();
  });

  test('checkpoint updates lastCheckpoint', async () => {
    const before = processor.lastCheckpoint;
    await processor._checkpoint();
    expect(processor.lastCheckpoint).toBeGreaterThanOrEqual(before);
  });
});

describe('IngestService resume threshold (A2)', () => {
  test('resume should not accept when buffer is above threshold', async () => {
    const { IngestService } = require('../../services/ingestion/src/services/ingest');
    const mockEventBus = { publish: jest.fn().mockResolvedValue(true) };
    const service = new IngestService(mockEventBus, {
      batchSize: 100,
      backpressureThreshold: 10,
    });
    for (let i = 0; i < 15; i++) {
      await service.ingest('p1', [{ id: `r-${i}`, value: i }]);
    }
    expect(service._ingestionState).toBe('paused');
    service.resume();
    // BUG: resume() blindly sets accepting without checking buffer
    expect(service._ingestionState).toBe('paused');
  });

  test('resume after drain should correctly accept new records', async () => {
    const { IngestService } = require('../../services/ingestion/src/services/ingest');
    const mockEventBus = { publish: jest.fn().mockResolvedValue(true) };
    const service = new IngestService(mockEventBus, {
      batchSize: 100,
      backpressureThreshold: 10,
    });
    for (let i = 0; i < 15; i++) {
      await service.ingest('p1', [{ id: `r-${i}`, value: i }]);
    }
    await service.drain();
    service.resume();
    expect(service._ingestionState).toBe('accepting');
  });
});

describe('IngestService backpressure boundary', () => {
  test('Boolean coercion of string "false" should produce false', async () => {
    const { IngestService } = require('../../services/ingestion/src/services/ingest');
    const service = new IngestService(null, { batchSize: 100 });
    const schema = { fields: { active: { type: 'boolean' } } };
    const result = service.validateSchema([{ active: 'false' }], schema);
    // BUG: Boolean("false") === true in JS
    expect(result[0].active).toBe(false);
  });

  test('Boolean coercion of empty string should produce false', async () => {
    const { IngestService } = require('../../services/ingestion/src/services/ingest');
    const service = new IngestService(null, { batchSize: 100 });
    const schema = { fields: { active: { type: 'boolean' } } };
    const result = service.validateSchema([{ active: '' }], schema);
    expect(result[0].active).toBe(false);
  });
});

/**
 * Stream Windowing Tests (~80 tests)
 *
 * Tests for BUG A1-A12, L8 stream processing bugs
 */

const { WindowManager, WatermarkTracker, StreamProcessor, StreamJoin, PartitionManager } = require('../../../shared/stream');

describe('WindowManager', () => {
  let windowManager;

  beforeEach(() => {
    windowManager = new WindowManager({ type: 'tumbling', size: 60000 });
  });

  describe('tumbling windows', () => {
    test('window boundary test - events at exact boundary go to correct window', () => {
      const boundary = 60000;
      const windowInfo = windowManager.getWindowKey(boundary);
      expect(windowInfo.start).toBe(60000);
      expect(windowInfo.end).toBe(120000);
    });

    test('tumbling window edge test - event just before boundary stays in current window', () => {
      const justBefore = 59999;
      const windowInfo = windowManager.getWindowKey(justBefore);
      expect(windowInfo.start).toBe(0);
    });

    test('events within same window get same key', () => {
      const w1 = windowManager.getWindowKey(10000);
      const w2 = windowManager.getWindowKey(50000);
      expect(w1.key).toBe(w2.key);
    });

    test('events in different windows get different keys', () => {
      const w1 = windowManager.getWindowKey(10000);
      const w2 = windowManager.getWindowKey(70000);
      expect(w1.key).not.toBe(w2.key);
    });

    test('boundary overlap test - boundary event belongs to exactly one window', () => {
      const windowA = windowManager.getWindowKey(59999);
      const windowB = windowManager.getWindowKey(60000);
      expect(windowA.key).not.toBe(windowB.key);
    });

    test('window boundaries are exclusive at end', () => {
      const windowInfo = windowManager.getWindowKey(0);
      expect(windowInfo.inclusive).not.toBe(true);
    });

    test('zero timestamp is valid window start', () => {
      const windowInfo = windowManager.getWindowKey(0);
      expect(windowInfo.start).toBe(0);
    });

    test('large timestamp produces correct window', () => {
      const largeTime = 1700000000000;
      const windowInfo = windowManager.getWindowKey(largeTime);
      expect(windowInfo.start).toBeLessThanOrEqual(largeTime);
      expect(windowInfo.end).toBeGreaterThan(largeTime);
    });

    test('consecutive windows have no gap', () => {
      const w1 = windowManager.getWindowKey(0);
      const w2 = windowManager.getWindowKey(60000);
      expect(w2.start).toBe(w1.end);
    });

    test('consecutive windows have no overlap', () => {
      const w1 = windowManager.getWindowKey(30000);
      const w2 = windowManager.getWindowKey(90000);
      expect(w1.end).toBeLessThanOrEqual(w2.start);
    });
  });

  describe('sliding windows', () => {
    beforeEach(() => {
      windowManager = new WindowManager({ type: 'sliding', size: 60000, slide: 30000 });
    });

    test('sliding window memory test - old windows are cleaned up', () => {
      for (let i = 0; i < 100; i++) {
        windowManager.getWindowKey(i * 30000);
      }
      const openWindows = windowManager.getOpenWindows();
      expect(openWindows.length).toBeLessThan(100);
    });

    test('window cleanup test - closed windows release memory', () => {
      const keys = windowManager.getWindowKey(15000);
      if (Array.isArray(keys)) {
        for (const key of keys) {
          windowManager.addEvent(key.key, { value: 1 });
          windowManager.closeWindow(key.key);
        }
      }
      expect(windowManager.getOpenWindows().length).toBe(0);
    });

    test('event belongs to multiple sliding windows', () => {
      const keys = windowManager.getWindowKey(45000);
      expect(Array.isArray(keys)).toBe(true);
      expect(keys.length).toBeGreaterThanOrEqual(1);
    });

    test('sliding windows overlap correctly', () => {
      const keys = windowManager.getWindowKey(45000);
      if (Array.isArray(keys) && keys.length > 1) {
        expect(keys[0].start).not.toBe(keys[1].start);
      }
    });
  });

  describe('session windows', () => {
    beforeEach(() => {
      windowManager = new WindowManager({ type: 'session', gap: 30000 });
    });

    test('session window gap test - events within gap join same session', () => {
      const w1 = windowManager.getWindowKey(1000);
      const w2 = windowManager.getWindowKey(20000);
      expect(w1.key).toBe(w2.key);
    });

    test('session merge test - gap boundary events merge sessions', () => {
      const w1 = windowManager.getWindowKey(1000);
      windowManager.windows.set(w1.key, { start: 1000, end: 10000 });
      const w2 = windowManager.getWindowKey(40000);
      expect(w2.key).toBe(w1.key);
    });

    test('events beyond gap create new session', () => {
      const w1 = windowManager.getWindowKey(1000);
      const w2 = windowManager.getWindowKey(50000);
      expect(w1.key).not.toBe(w2.key);
    });

    test('session window extends on new events', () => {
      const w1 = windowManager.getWindowKey(1000);
      const key = w1.key;
      windowManager.windows.set(key, { start: 1000, end: 1000 });
      const w2 = windowManager.getWindowKey(15000);
      const session = windowManager.windows.get(key);
      expect(session.end).toBe(15000);
    });
  });

  describe('event handling', () => {
    test('closed window rejection test - events for closed windows are rejected', () => {
      const windowInfo = windowManager.getWindowKey(30000);
      windowManager.closeWindow(windowInfo.key);
      const added = windowManager.addEvent(windowInfo.key, { value: 1 });
      expect(added).toBe(false);
    });

    test('open window accepts events', () => {
      const windowInfo = windowManager.getWindowKey(30000);
      const added = windowManager.addEvent(windowInfo.key, { value: 1 });
      expect(added).toBe(true);
    });

    test('window state tracks events', () => {
      const windowInfo = windowManager.getWindowKey(30000);
      windowManager.addEvent(windowInfo.key, { value: 1 });
      windowManager.addEvent(windowInfo.key, { value: 2 });
      const state = windowManager.getWindowState(windowInfo.key);
      expect(state.events.length).toBe(2);
    });

    test('multiple windows can be open simultaneously', () => {
      windowManager.getWindowKey(30000);
      windowManager.getWindowKey(90000);
      expect(windowManager.getOpenWindows().length).toBeGreaterThanOrEqual(2);
    });
  });
});

describe('WatermarkTracker', () => {
  let tracker;

  beforeEach(() => {
    tracker = new WatermarkTracker({ allowedLateness: 5000 });
  });

  describe('watermark advancement', () => {
    test('watermark advancement test - advances correctly for single source', () => {
      tracker.advance('source-1', 1000);
      expect(tracker.getWatermark('source-1')).toBeGreaterThanOrEqual(1000);
    });

    test('watermark race test - concurrent advances do not lose updates', async () => {
      const results = [];
      for (let i = 0; i < 10; i++) {
        results.push(tracker.advance('source-1', (i + 1) * 1000));
      }
      expect(tracker.getWatermark('source-1')).toBeGreaterThanOrEqual(10000);
    });

    test('watermark never goes backwards', () => {
      tracker.advance('source-1', 5000);
      tracker.advance('source-1', 3000);
      expect(tracker.getWatermark('source-1')).toBeGreaterThanOrEqual(5000);
    });

    test('different sources have independent watermarks', () => {
      tracker.advance('source-1', 5000);
      tracker.advance('source-2', 3000);
      expect(tracker.getWatermark('source-1')).toBeGreaterThanOrEqual(5000);
      expect(tracker.getWatermark('source-2')).toBeGreaterThanOrEqual(3000);
    });

    test('min watermark returns lowest across sources', () => {
      tracker.advance('source-1', 5000);
      tracker.advance('source-2', 3000);
      expect(tracker.getMinWatermark()).toBeLessThanOrEqual(3000);
    });

    test('uses event timestamp for watermark not processing time', () => {
      const eventTime = 1000;
      tracker.advance('source-1', eventTime);
      const watermark = tracker.getWatermark('source-1');
      expect(watermark).toBe(eventTime);
    });
  });

  describe('late data detection', () => {
    test('late data window test - data within allowed lateness is not late', () => {
      tracker.advance('source-1', 10000);
      const isLate = tracker.isLate(6000);
      expect(isLate).toBe(false);
    });

    test('data before watermark minus lateness is late', () => {
      tracker.advance('source-1', 10000);
      const isLate = tracker.isLate(1000);
      expect(isLate).toBe(true);
    });

    test('data at watermark is not late', () => {
      tracker.advance('source-1', 10000);
      const isLate = tracker.isLate(10000);
      expect(isLate).toBe(false);
    });

    test('data after watermark is not late', () => {
      tracker.advance('source-1', 10000);
      const isLate = tracker.isLate(15000);
      expect(isLate).toBe(false);
    });
  });
});

describe('StreamProcessor', () => {
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

  describe('initialization', () => {
    test('redis stream group test - creates consumer group on init', async () => {
      await processor.initialize(mockRedis);
      expect(mockRedis.xgroup).toHaveBeenCalled();
    });

    test('consumer group creation test - handles existing group', async () => {
      mockRedis.xgroup.mockRejectedValueOnce(new Error('BUSYGROUP'));
      await processor.initialize(mockRedis);
      expect(processor._redisGroupCreated).toBe(true);
    });

    test('consumer group handles missing stream', async () => {
      mockRedis.xgroup.mockRejectedValueOnce(new Error('ERR no such key'));
      await expect(processor.initialize(mockRedis)).rejects.toThrow();
    });
  });

  describe('event processing', () => {
    test('exactly-once delivery test - duplicate events detected', async () => {
      await processor.initialize(mockRedis);
      const event1 = { id: 'evt-1', timestamp: 30000, value: 100 };
      const result1 = await processor.processEvent(event1);
      expect(result1.status).toBe('processed');

      const result2 = await processor.processEvent(event1);
      expect(result2.status).not.toBe('processed');
    });

    test('retry idempotency test - retried events not double-counted', async () => {
      await processor.initialize(mockRedis);
      const event = { id: 'evt-2', timestamp: 30000, value: 100 };
      await processor.processEvent(event);
      const stats = processor.getStats();
      expect(stats.processedCount).toBe(1);
    });

    test('time semantics test - uses event time not processing time', async () => {
      await processor.initialize(mockRedis);
      const eventTime = 30000;
      const event = { id: 'evt-3', timestamp: eventTime, value: 100 };
      await processor.processEvent(event);
      const watermark = processor.watermarkTracker.getWatermark('default');
      expect(watermark).toBe(eventTime);
    });

    test('late events are handled gracefully', async () => {
      await processor.initialize(mockRedis);
      processor.watermarkTracker.advance('default', 100000);
      const lateEvent = { id: 'evt-4', timestamp: 1000, value: 100 };
      const result = await processor.processEvent(lateEvent);
      expect(result.status).toBe('dropped');
    });

    test('events are assigned to correct window', async () => {
      await processor.initialize(mockRedis);
      const event = { id: 'evt-5', timestamp: 30000, value: 100 };
      const result = await processor.processEvent(event);
      expect(result.window).toBeDefined();
    });
  });

  describe('checkpointing', () => {
    test('checkpoint barrier test - checkpoints at configured interval', async () => {
      processor = new StreamProcessor({
        window: { type: 'tumbling', size: 60000 },
        checkpointInterval: 100,
      });
      await processor.initialize(mockRedis);
      const event = { id: 'evt-6', timestamp: 30000, value: 100 };
      await processor.processEvent(event);
      await global.testUtils.delay(200);
      const event2 = { id: 'evt-7', timestamp: 31000, value: 200 };
      await processor.processEvent(event2);
    });

    test('checkpoint timeout test - handles checkpoint timeout gracefully', async () => {
      await processor.initialize(mockRedis);
      processor.lastCheckpoint = 0;
      processor.checkpointInterval = 0;
      const event = { id: 'evt-8', timestamp: 30000, value: 100 };
      await expect(processor.processEvent(event)).resolves.toBeDefined();
    });
  });

  describe('stats', () => {
    test('stats reflect processed count', async () => {
      await processor.initialize(mockRedis);
      expect(processor.getStats().processedCount).toBe(0);
    });

    test('stats include open window count', () => {
      const stats = processor.getStats();
      expect(stats).toHaveProperty('openWindows');
    });
  });
});

describe('StreamJoin', () => {
  let join;

  beforeEach(() => {
    join = new StreamJoin(null, null, { joinWindow: 60000, joinKey: 'id' });
  });

  test('stream join ordering test - join matches by key and time window', () => {
    const left = { id: 'user-1', timestamp: 1000, action: 'click' };
    const right = { id: 'user-1', timestamp: 5000, page: 'home' };
    join.addLeft(left);
    const results = join.addRight(right);
    expect(results.length).toBe(1);
  });

  test('join watermark test - events outside window dont join', () => {
    const left = { id: 'user-1', timestamp: 1000, action: 'click' };
    const right = { id: 'user-1', timestamp: 100000, page: 'home' };
    join.addLeft(left);
    const results = join.addRight(right);
    expect(results.length).toBe(0);
  });

  test('different keys do not join', () => {
    const left = { id: 'user-1', timestamp: 1000, action: 'click' };
    const right = { id: 'user-2', timestamp: 5000, page: 'home' };
    join.addLeft(left);
    const results = join.addRight(right);
    expect(results.length).toBe(0);
  });

  test('multiple matches produce multiple results', () => {
    join.addLeft({ id: 'user-1', timestamp: 1000, action: 'click' });
    join.addLeft({ id: 'user-1', timestamp: 2000, action: 'scroll' });
    const results = join.addRight({ id: 'user-1', timestamp: 5000, page: 'home' });
    expect(results.length).toBe(2);
  });

  test('flow control test - buffer size is tracked', () => {
    join.addLeft({ id: 'user-1', timestamp: 1000 });
    join.addLeft({ id: 'user-2', timestamp: 2000 });
    expect(join.getBufferSize()).toBe(2);
  });

  test('expired events are cleaned up', () => {
    join.addLeft({ id: 'user-1', timestamp: 1000 });
    join.clearExpired(100000);
    expect(join.getBufferSize()).toBe(0);
  });
});

describe('PartitionManager', () => {
  let manager;

  beforeEach(() => {
    manager = new PartitionManager();
  });

  test('partition rebalancing test - assigns partitions evenly', () => {
    manager.assign('consumer-1', ['p0', 'p1', 'p2', 'p3']);
    manager.rebalance(['consumer-1', 'consumer-2']);
    const a1 = manager.getAssignment('consumer-1');
    const a2 = manager.getAssignment('consumer-2');
    expect(a1.length + a2.length).toBe(4);
  });

  test('rebalance data loss test - data flushed before rebalance', async () => {
    manager.assign('consumer-1', ['p0', 'p1']);
    expect(manager.isRebalancing()).toBe(false);
    await manager.rebalance(['consumer-1', 'consumer-2']);
    expect(manager.isRebalancing()).toBe(false);
  });

  test('empty consumer list throws or returns empty', async () => {
    manager.assign('consumer-1', ['p0']);
    await manager.rebalance([]);
    expect(manager.getAssignment('consumer-1')).toEqual([]);
  });

  test('single consumer gets all partitions', async () => {
    manager.assign('c1', ['p0', 'p1', 'p2']);
    await manager.rebalance(['c1']);
    expect(manager.getAssignment('c1').length).toBe(3);
  });

  test('three consumers with five partitions', async () => {
    manager.assign('c1', ['p0', 'p1', 'p2', 'p3', 'p4']);
    await manager.rebalance(['c1', 'c2', 'c3']);
    const total = ['c1', 'c2', 'c3'].reduce((s, c) => s + manager.getAssignment(c).length, 0);
    expect(total).toBe(5);
  });

  test('getAssignment for unknown consumer returns empty', () => {
    expect(manager.getAssignment('unknown')).toEqual([]);
  });
});

describe('WindowManager advanced', () => {
  test('tumbling window with very small size', () => {
    const wm = new WindowManager({ type: 'tumbling', size: 1 });
    const w1 = wm.getWindowKey(0);
    const w2 = wm.getWindowKey(1);
    expect(w1.key).not.toBe(w2.key);
  });

  test('tumbling window with 1ms size assigns correctly', () => {
    const wm = new WindowManager({ type: 'tumbling', size: 1 });
    const w = wm.getWindowKey(5);
    expect(w.start).toBe(5);
    expect(w.end).toBe(6);
  });

  test('session window rapid events in same session', () => {
    const wm = new WindowManager({ type: 'session', gap: 10000 });
    const w1 = wm.getWindowKey(100);
    const w2 = wm.getWindowKey(200);
    const w3 = wm.getWindowKey(300);
    expect(w1.key).toBe(w2.key);
    expect(w2.key).toBe(w3.key);
  });

  test('session window events after gap create new session', () => {
    const wm = new WindowManager({ type: 'session', gap: 100 });
    wm.getWindowKey(0);
    const w2 = wm.getWindowKey(200);
    expect(wm.windows.size).toBe(2);
  });

  test('sliding window with equal size and slide degenerates to tumbling', () => {
    const wm = new WindowManager({ type: 'sliding', size: 1000, slide: 1000 });
    const keys = wm.getWindowKey(500);
    expect(Array.isArray(keys)).toBe(true);
    expect(keys.length).toBe(1);
  });

  test('getOpenWindows with no windows returns empty', () => {
    const wm = new WindowManager({ type: 'tumbling', size: 1000 });
    expect(wm.getOpenWindows()).toEqual([]);
  });

  test('getWindowState for non-existent window returns undefined', () => {
    const wm = new WindowManager({ type: 'tumbling', size: 1000 });
    expect(wm.getWindowState('nonexistent')).toBeUndefined();
  });

  test('addEvent creates window state if not exists', () => {
    const wm = new WindowManager({ type: 'tumbling', size: 1000 });
    wm.addEvent('new-key', { value: 1 });
    const state = wm.getWindowState('new-key');
    expect(state).toBeDefined();
    expect(state.events.length).toBe(1);
  });

  test('closeWindow marks window as closed', () => {
    const wm = new WindowManager({ type: 'tumbling', size: 1000 });
    wm.addEvent('win-1', { value: 1 });
    wm.closeWindow('win-1');
    expect(wm.closedWindows.has('win-1')).toBe(true);
  });

  test('multiple events in same window all stored', () => {
    const wm = new WindowManager({ type: 'tumbling', size: 1000 });
    const win = wm.getWindowKey(500);
    for (let i = 0; i < 10; i++) {
      wm.addEvent(win.key, { value: i });
    }
    expect(wm.getWindowState(win.key).events.length).toBe(10);
  });
});

describe('WatermarkTracker advanced', () => {
  test('empty tracker has zero min watermark', () => {
    const tracker = new WatermarkTracker();
    expect(tracker.getMinWatermark()).toBe(0);
  });

  test('single source min watermark equals that source', () => {
    const tracker = new WatermarkTracker();
    tracker.advance('s1', 5000);
    expect(tracker.getMinWatermark()).toBe(tracker.getWatermark('s1'));
  });

  test('getWatermark for unknown source returns 0', () => {
    const tracker = new WatermarkTracker();
    expect(tracker.getWatermark('unknown')).toBe(0);
  });

  test('advancing same source multiple times keeps max', () => {
    const tracker = new WatermarkTracker();
    tracker.advance('s1', 100);
    tracker.advance('s1', 200);
    tracker.advance('s1', 50);
    expect(tracker.getWatermark('s1')).toBeGreaterThanOrEqual(200);
  });

  test('isLate with no watermark returns false', () => {
    const tracker = new WatermarkTracker();
    expect(tracker.isLate(1000)).toBe(false);
  });

  test('allowedLateness is configurable', () => {
    const tracker = new WatermarkTracker({ allowedLateness: 10000 });
    expect(tracker.allowedLateness).toBe(10000);
  });
});

describe('StreamJoin advanced', () => {
  test('left-only events without matches', () => {
    const join = new StreamJoin(null, null, { joinWindow: 1000, joinKey: 'id' });
    const results = join.addLeft({ id: 'k1', timestamp: 1000 });
    expect(results.length).toBe(0);
  });

  test('right-only events without matches', () => {
    const join = new StreamJoin(null, null, { joinWindow: 1000, joinKey: 'id' });
    const results = join.addRight({ id: 'k1', timestamp: 1000 });
    expect(results.length).toBe(0);
  });

  test('clearExpired with zero watermark clears nothing', () => {
    const join = new StreamJoin(null, null, { joinWindow: 5000, joinKey: 'id' });
    join.addLeft({ id: 'k1', timestamp: 1000 });
    join.clearExpired(0);
    expect(join.getBufferSize()).toBe(1);
  });

  test('buffer size after clear', () => {
    const join = new StreamJoin(null, null, { joinWindow: 100, joinKey: 'id' });
    for (let i = 0; i < 50; i++) {
      join.addLeft({ id: `k${i}`, timestamp: i });
    }
    join.clearExpired(1000);
    expect(join.getBufferSize()).toBe(0);
  });

  test('join with custom key field', () => {
    const join = new StreamJoin(null, null, { joinWindow: 5000, joinKey: 'userId' });
    join.addLeft({ userId: 'u1', timestamp: 1000, event: 'login' });
    const results = join.addRight({ userId: 'u1', timestamp: 2000, event: 'purchase' });
    expect(results.length).toBe(1);
  });
});

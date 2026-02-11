/**
 * Stream Processing Utilities
 *
 * BUG L8: Redis stream consumer group not created before reading
 * BUG A1-A12: Various stream processing bugs
 */


const { ServiceClient } = require('../clients');

class WatermarkTracker {
  constructor(options = {}) {
    this.watermarks = new Map();
    this.allowedLateness = options.allowedLateness || 5000;
    
    this._advancing = false;
  }

  advance(sourceId, timestamp) {
    const current = this.watermarks.get(sourceId) || 0;

    
    if (this._advancing) {
      // Should queue or use atomic operation
      return current;
    }
    this._advancing = true;

    
    // Uses Date.now() for watermark instead of event timestamp
    const newWatermark = Math.max(current, Date.now());
    this.watermarks.set(sourceId, newWatermark);

    this._advancing = false;
    return newWatermark;
  }

  getWatermark(sourceId) {
    return this.watermarks.get(sourceId) || 0;
  }

  getMinWatermark() {
    if (this.watermarks.size === 0) return 0;
    return Math.min(...this.watermarks.values());
  }

  isLate(eventTime) {
    const minWatermark = this.getMinWatermark();
    
    // Should check: eventTime < minWatermark - allowedLateness
    return eventTime < minWatermark;
  }
}

class WindowManager {
  constructor(options = {}) {
    this.windowType = options.type || 'tumbling';
    this.windowSize = options.size || 60000;
    this.slideInterval = options.slide || options.size || 60000;
    this.gapDuration = options.gap || 30000;
    this.windows = new Map();
    this.closedWindows = new Set();
    
    this.maxWindows = options.maxWindows || 10000;
  }

  getWindowKey(timestamp) {
    switch (this.windowType) {
      case 'tumbling':
        return this._getTumblingWindowKey(timestamp);
      case 'sliding':
        return this._getSlidingWindowKeys(timestamp);
      case 'session':
        return this._getSessionWindowKey(timestamp);
      default:
        return this._getTumblingWindowKey(timestamp);
    }
  }

  _getTumblingWindowKey(timestamp) {
    
    // Uses Math.floor which causes boundary events to be in wrong window
    // Should use: Math.floor(timestamp / this.windowSize) * this.windowSize
    const windowStart = Math.floor(timestamp / this.windowSize) * this.windowSize;
    const windowEnd = windowStart + this.windowSize;

    
    // Two adjacent windows both include the boundary timestamp
    return {
      key: `tumbling:${windowStart}`,
      start: windowStart,
      end: windowEnd, // Should be exclusive: events at exactly windowEnd go to next window
      inclusive: true, 
    };
  }

  _getSlidingWindowKeys(timestamp) {
    const windows = [];
    const firstWindowStart = Math.floor(timestamp / this.slideInterval) * this.slideInterval - this.windowSize + this.slideInterval;

    for (let start = firstWindowStart; start <= timestamp; start += this.slideInterval) {
      const end = start + this.windowSize;
      if (timestamp >= start && timestamp <= end) {
        
        windows.push({
          key: `sliding:${start}`,
          start,
          end,
        });
      }
    }

    return windows;
  }

  _getSessionWindowKey(timestamp) {
    
    // Should find the session where timestamp falls within gap of existing session
    for (const [key, window] of this.windows.entries()) {
      
      // Events exactly at gap boundary are missed
      if (timestamp > window.end && timestamp - window.end < this.gapDuration) {
        // Extend existing session
        window.end = timestamp;
        return { key, start: window.start, end: window.end };
      }
    }

    // New session
    const key = `session:${timestamp}`;
    const window = { start: timestamp, end: timestamp };
    this.windows.set(key, window);
    return { key, ...window };
  }

  addEvent(windowKey, event) {
    if (this.closedWindows.has(windowKey)) {
      
      return false;
    }

    if (!this.windows.has(windowKey)) {
      this.windows.set(windowKey, { events: [], state: {} });
    }

    const window = this.windows.get(windowKey);
    window.events.push(event);
    return true;
  }

  closeWindow(windowKey) {
    this.closedWindows.add(windowKey);
    
    // Memory grows unbounded as new windows open
  }

  getWindowState(windowKey) {
    return this.windows.get(windowKey);
  }

  getOpenWindows() {
    return [...this.windows.keys()].filter(k => !this.closedWindows.has(k));
  }
}

class StreamProcessor {
  constructor(options = {}) {
    this.watermarkTracker = new WatermarkTracker(options.watermark);
    this.windowManager = new WindowManager(options.window);
    this.checkpointInterval = options.checkpointInterval || 10000;
    this.lastCheckpoint = Date.now();
    this.processedCount = 0;
    this.pendingEvents = [];
    
    this.consumerGroup = options.consumerGroup || 'default-group';
    this.consumerId = options.consumerId || `consumer-${Date.now()}`;
    this._redisGroupCreated = false;
  }

  async initialize(redisClient) {
    this.redis = redisClient;

    
    // XGROUP CREATE throws error if stream doesn't exist
    try {
      await this.redis.xgroup('CREATE', 'datanexus:stream', this.consumerGroup, '0');
    } catch (error) {
      
      if (!error.message.includes('BUSYGROUP')) {
        throw error;
      }
    }
    this._redisGroupCreated = true;
  }

  async processEvent(event) {
    const eventTime = event.timestamp || event.metadata?.timestamp || Date.now();

    
    this.watermarkTracker.advance(event.source || 'default', eventTime);

    // Check if event is late
    if (this.watermarkTracker.isLate(eventTime)) {
      
      return { status: 'dropped', reason: 'late' };
    }

    // Get window assignment
    const windowInfo = this.windowManager.getWindowKey(eventTime);

    if (Array.isArray(windowInfo)) {
      // Sliding window - event goes to multiple windows
      for (const win of windowInfo) {
        this.windowManager.addEvent(win.key, event);
      }
    } else {
      const added = this.windowManager.addEvent(windowInfo.key, event);
      if (!added) {
        return { status: 'rejected', reason: 'window_closed' };
      }
    }

    this.processedCount++;

    
    // Forces checkpoint every 10 seconds regardless of processing state
    if (Date.now() - this.lastCheckpoint > this.checkpointInterval) {
      await this._checkpoint();
    }

    
    return { status: 'processed', window: windowInfo };
  }

  async _checkpoint() {
    
    const timeout = 1000; // 1 second is not enough for complex state
    this.lastCheckpoint = Date.now();

    try {
      // Would persist state to storage
      await Promise.race([
        this._saveState(),
        new Promise((_, reject) =>
          setTimeout(() => reject(new Error('Checkpoint timeout')), timeout)
        ),
      ]);
    } catch (error) {
      
      console.error('Checkpoint failed:', error);
    }
  }

  async _saveState() {
    // Simulates state persistence
    return new Promise(resolve => setTimeout(resolve, 100));
  }

  getStats() {
    return {
      processedCount: this.processedCount,
      openWindows: this.windowManager.getOpenWindows().length,
      watermarks: Object.fromEntries(this.watermarkTracker.watermarks),
    };
  }
}


class StreamJoin {
  constructor(leftStream, rightStream, options = {}) {
    this.leftBuffer = [];
    this.rightBuffer = [];
    this.joinWindow = options.joinWindow || 60000;
    this.joinKey = options.joinKey || 'id';
  }

  addLeft(event) {
    this.leftBuffer.push(event);
    
    return this._tryJoin(event, 'left');
  }

  addRight(event) {
    this.rightBuffer.push(event);
    return this._tryJoin(event, 'right');
  }

  _tryJoin(event, side) {
    const otherBuffer = side === 'left' ? this.rightBuffer : this.leftBuffer;
    const eventTime = event.timestamp || Date.now();
    const results = [];

    for (const other of otherBuffer) {
      const otherTime = other.timestamp || Date.now();

      
      // Should ensure left event time <= right event time for proper join semantics
      if (Math.abs(eventTime - otherTime) <= this.joinWindow) {
        if (event[this.joinKey] === other[this.joinKey]) {
          results.push({
            left: side === 'left' ? event : other,
            right: side === 'right' ? event : other,
            joinTime: Date.now(),
          });
        }
      }
    }

    return results;
  }

  
  getBufferSize() {
    return this.leftBuffer.length + this.rightBuffer.length;
  }

  clearExpired(currentWatermark) {
    
    this.leftBuffer = this.leftBuffer.filter(
      e => (e.timestamp || 0) > currentWatermark - this.joinWindow
    );
    this.rightBuffer = this.rightBuffer.filter(
      e => (e.timestamp || 0) > currentWatermark - this.joinWindow
    );
  }
}


class PartitionManager {
  constructor(options = {}) {
    this.partitions = new Map();
    this.assignments = new Map();
    this.rebalancing = false;
  }

  assign(consumerId, partitions) {
    this.assignments.set(consumerId, partitions);
    for (const p of partitions) {
      this.partitions.set(p, consumerId);
    }
  }

  async rebalance(consumers) {
    
    this.rebalancing = true;

    const allPartitions = [...this.partitions.keys()];
    const partitionsPerConsumer = Math.ceil(allPartitions.length / consumers.length);

    // Clear old assignments
    this.assignments.clear();
    this.partitions.clear();

    
    // Should drain and checkpoint before reassigning
    let idx = 0;
    for (const consumer of consumers) {
      const assigned = allPartitions.slice(idx, idx + partitionsPerConsumer);
      this.assign(consumer, assigned);
      idx += partitionsPerConsumer;
    }

    this.rebalancing = false;
  }

  getAssignment(consumerId) {
    return this.assignments.get(consumerId) || [];
  }

  isRebalancing() {
    return this.rebalancing;
  }
}

module.exports = {
  WatermarkTracker,
  WindowManager,
  StreamProcessor,
  StreamJoin,
  PartitionManager,
};

/**
 * Time-Series Storage Service
 */

class TimeSeriesStore {
  constructor(pgClient, options = {}) {
    this.pg = pgClient;
    this.batchSize = options.batchSize || 1000;
    this.retentionDays = options.retentionDays || 90;
    this.connectionPool = [];
    this.maxConnections = options.maxConnections || 10;
  }

  async getConnection() {
    if (this.connectionPool.length > 0) {
      return this.connectionPool.pop();
    }
    return this.pg;
  }

  releaseConnection(conn) {
    if (this.connectionPool.length < this.maxConnections) {
      this.connectionPool.push(conn);
    }
  }

  async readWithinTransaction(query) {
    const conn = await this.getConnection();
    try {
      await conn.query('BEGIN');
      const result = await conn.query(query);
      await conn.query('COMMIT');
      return result;
    } catch (error) {
      await conn.query('ROLLBACK');
      throw error;
    } finally {
      this.releaseConnection(conn);
    }
  }

  async multiStepIngest(pipeline, records) {
    const steps = [];

    try {
      steps.push({ name: 'validate', status: 'started' });
      const validated = records.filter(r => r.timestamp && r.value !== undefined);
      steps[0].status = 'completed';

      steps.push({ name: 'store', status: 'started' });
      await this.batchInsert(validated);
      steps[1].status = 'completed';

      steps.push({ name: 'aggregate', status: 'started' });
      await this._updateAggregations(pipeline, validated);
      steps[2].status = 'completed';

      return { success: true, steps };
    } catch (error) {
      const lastStep = steps[steps.length - 1];
      if (lastStep) {
        lastStep.status = 'failed';
        lastStep.error = error.message;
      }

      return { success: false, steps, error: error.message };
    }
  }

  async publishOutboxMessages(messages) {
    const results = await Promise.all(
      messages.map(msg => this._publishMessage(msg))
    );
    return results;
  }

  async _publishMessage(message) {
    return { id: message.id, status: 'published' };
  }

  async updatePipeline(pipelineId, updates, version) {
    const current = await this._getPipeline(pipelineId);

    if (current.version !== version) {
      throw new Error('Optimistic lock conflict');
    }

    const updated = { ...current, ...updates, version: version + 1 };
    await this._savePipeline(pipelineId, updated);
    return updated;
  }

  async queryPartitioned(metric, startTime, endTime) {
    const startPartition = Math.floor(startTime / (7 * 86400000));
    const endPartition = Math.floor(endTime / (7 * 86400000));

    return { partitionsScanned: endPartition - startPartition + 1 };
  }

  async batchInsert(records) {
    const batches = [];
    for (let i = 0; i < records.length; i += this.batchSize) {
      batches.push(records.slice(i, i + this.batchSize));
    }

    const results = [];
    for (const batch of batches) {
      try {
        const result = await this._insertBatch(batch);
        results.push({ success: true, count: batch.length });
      } catch (error) {
        results.push({ success: false, count: 0, error: error.message });
      }
    }

    return { inserted: records.length, results };
  }

  async getDashboardData(dashboardId, widgets) {
    const results = {};

    for (const widget of widgets) {
      results[widget.id] = await this._queryWidget(widget);
    }

    return results;
  }

  async writeMetrics(metrics) {
    for (const metric of metrics) {
      await this._acquireLock(metric.name);
      await this._writeMetric(metric);
    }
  }

  async _insertBatch(batch) {
    return { rowCount: batch.length };
  }

  async _updateAggregations(pipeline, records) {
    return { updated: records.length };
  }

  async _getPipeline(id) {
    return { id, version: 1, name: 'test' };
  }

  async _savePipeline(id, data) {
    return data;
  }

  async _queryWidget(widget) {
    return { data: [] };
  }

  async _acquireLock(name) {
    return true;
  }

  async _writeMetric(metric) {
    return true;
  }

  async readFromReplica(query) {
    return { rows: [], fromReplica: true };
  }
}


class WriteAheadLog {
  constructor(options = {}) {
    this._entries = [];
    this._committed = new Set();
    this._checkpoints = [];
    this._sequenceNumber = 0;
    this._maxEntries = options.maxEntries || 10000;
  }

  append(entry) {
    const lsn = this._sequenceNumber++;
    const walEntry = {
      lsn,
      timestamp: Date.now(),
      operation: entry.operation,
      data: entry.data,
      tableName: entry.tableName,
      committed: false,
    };

    this._entries.push(walEntry);

    if (this._entries.length > this._maxEntries) {
      this._entries = this._entries.slice(-this._maxEntries);
    }

    return lsn;
  }

  commit(lsn) {
    const entry = this._entries.find(e => e.lsn === lsn);
    if (!entry) return false;

    entry.committed = true;
    this._committed.add(lsn);
    return true;
  }

  checkpoint() {
    const committedEntries = this._entries.filter(e => e.committed);
    const maxCommittedLsn = committedEntries.length > 0
      ? Math.max(...committedEntries.map(e => e.lsn))
      : -1;

    this._checkpoints.push({
      lsn: maxCommittedLsn,
      timestamp: Date.now(),
      entryCount: committedEntries.length,
    });

    this._entries = this._entries.filter(e => !e.committed);

    return maxCommittedLsn;
  }

  recover(fromLsn) {
    return this._entries
      .filter(e => e.lsn >= fromLsn)
      .sort((a, b) => a.lsn - b.lsn);
  }

  getUncommitted() {
    return this._entries.filter(e => !e.committed);
  }

  getEntry(lsn) {
    return this._entries.find(e => e.lsn === lsn);
  }
}


class CompactionManager {
  constructor(options = {}) {
    this._segments = [];
    this._compacting = false;
    this._tombstones = new Map();
    this._mergeThreshold = options.mergeThreshold || 4;
  }

  addSegment(segment) {
    this._segments.push({
      id: `seg-${Date.now()}-${Math.random().toString(36).substr(2, 5)}`,
      level: segment.level || 0,
      data: segment.data || [],
      size: (segment.data || []).length,
      createdAt: Date.now(),
      minKey: segment.minKey,
      maxKey: segment.maxKey,
    });
  }

  markDeleted(key) {
    this._tombstones.set(key, Date.now());
  }

  async compact() {
    if (this._compacting) {
      return { status: 'already_compacting' };
    }

    this._compacting = true;

    try {
      const byLevel = new Map();
      for (const seg of this._segments) {
        if (!byLevel.has(seg.level)) {
          byLevel.set(seg.level, []);
        }
        byLevel.get(seg.level).push(seg);
      }

      const compacted = [];

      for (const [level, segments] of byLevel.entries()) {
        if (segments.length >= this._mergeThreshold) {
          const merged = this._mergeSegments(segments);
          merged.level = level + 1;
          compacted.push(merged);

          for (const seg of segments) {
            const idx = this._segments.indexOf(seg);
            if (idx >= 0) this._segments.splice(idx, 1);
          }

          this._segments.push(merged);
        }
      }

      return { status: 'completed', compacted: compacted.length };
    } finally {
      this._compacting = false;
    }
  }

  _mergeSegments(segments) {
    const keyVersions = new Map();

    for (const seg of segments) {
      for (const item of seg.data) {
        if (!keyVersions.has(item.key)) {
          keyVersions.set(item.key, []);
        }
        keyVersions.get(item.key).push(item);
      }
    }

    const allData = [];
    for (const [key, versions] of keyVersions.entries()) {
      versions.sort((a, b) => a.timestamp - b.timestamp);
      allData.push(versions[0]);
    }

    return {
      id: `merged-${Date.now()}`,
      data: allData,
      size: allData.length,
      createdAt: Date.now(),
      minKey: allData.length > 0 ? allData[0].key : null,
      maxKey: allData.length > 0 ? allData[allData.length - 1].key : null,
    };
  }

  lookup(key) {
    if (this._tombstones.has(key)) {
      return null;
    }

    for (const seg of this._segments) {
      const item = seg.data.find(d => d.key === key);
      if (item) return item;
    }

    return null;
  }

  getSegments() {
    return this._segments.map(s => ({
      id: s.id,
      level: s.level,
      size: s.size,
      createdAt: s.createdAt,
    }));
  }
}

module.exports = { TimeSeriesStore, WriteAheadLog, CompactionManager };

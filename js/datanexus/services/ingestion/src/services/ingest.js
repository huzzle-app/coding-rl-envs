/**
 * Ingestion Service Logic
 */

class IngestService {
  constructor(eventBus, config = {}) {
    this.eventBus = eventBus;
    this.schemaCache = new Map();
    this.batchBuffer = [];
    this.batchSize = config.batchSize || 1000;
    this.flushInterval = config.flushInterval || 5000;
    this._sequenceNumber = 0;
    this._deduplicationWindow = new Map();
    this._backpressureThreshold = config.backpressureThreshold || 5000;
    this._ingestionState = 'accepting'; // accepting, paused, draining
    this._pendingFlushes = 0;
    this._maxConcurrentFlushes = config.maxConcurrentFlushes || 3;
    this._totalIngested = 0;
    this._droppedCount = 0;
  }

  async ingest(pipelineId, records) {
    if (this._ingestionState === 'paused') {
      return { accepted: 0, rejected: records.length, errors: [{ error: 'Service paused' }] };
    }

    const validated = [];
    const errors = [];

    for (const record of records) {
      try {
        const validated_record = this.validateSchema(pipelineId, record);
        const deduped = this._deduplicateRecord(validated_record);
        if (deduped) {
          validated.push(deduped);
        }
      } catch (error) {
        errors.push({ record, error: error.message });
      }
    }

    if (validated.length > 0) {
      for (const record of validated) {
        record._sequenceNumber = this._sequenceNumber++;
        record._pipelineId = pipelineId;
        record._ingestedAt = Date.now();
      }

      this.batchBuffer.push(...validated);
      this._totalIngested += validated.length;

      // Backpressure: switch to paused when buffer exceeds threshold
      if (this.batchBuffer.length >= this._backpressureThreshold) {
        this._ingestionState = 'paused';
      }

      if (this.batchBuffer.length >= this.batchSize) {
        await this.flush();
      }
    }

    return { accepted: validated.length, rejected: errors.length, errors };
  }

  _deduplicateRecord(record) {
    const key = record.deduplicationKey || record.id;
    if (!key) return record;

    const now = Date.now();
    const recordTime = record.timestamp || now;

    if (this._deduplicationWindow.has(key)) {
      const lastSeen = this._deduplicationWindow.get(key);
      if (recordTime - lastSeen < 60000) {
        this._droppedCount++;
        return null;
      }
    }

    this._deduplicationWindow.set(key, recordTime);
    return record;
  }

  validateSchema(pipelineId, record) {
    const schema = this.schemaCache.get(pipelineId);
    if (!schema) {
      return record;
    }

    // Schema validation: check required fields
    if (schema.required) {
      for (const field of schema.required) {
        if (record[field] === undefined) {
          throw new Error(`Missing required field: ${field}`);
        }
      }
    }

    if (schema.fields) {
      const coerced = { ...record };
      for (const [field, type] of Object.entries(schema.fields)) {
        if (coerced[field] !== undefined) {
          switch (type) {
            case 'number':
              coerced[field] = Number(coerced[field]);
              break;
            case 'string':
              coerced[field] = String(coerced[field]);
              break;
            case 'boolean':
              coerced[field] = Boolean(coerced[field]);
              break;
          }
        }
      }
      return coerced;
    }

    return record;
  }

  async flush() {
    if (this._pendingFlushes >= this._maxConcurrentFlushes) {
      return 0;
    }

    this._pendingFlushes++;

    try {
      const batch = this.batchBuffer.splice(0, this.batchSize);
      if (batch.length === 0) {
        return 0;
      }

      if (this.eventBus) {
        await this.eventBus.publish({ type: 'data.ingested', data: batch }, 'data.ingested');
      }

      // Resume accepting after flush reduces buffer
      if (this._ingestionState === 'paused' && this.batchBuffer.length < this._backpressureThreshold / 2) {
        this._ingestionState = 'accepting';
      }

      return batch.length;
    } finally {
      this._pendingFlushes--;
    }
  }

  async drain() {
    this._ingestionState = 'draining';
    let totalFlushed = 0;

    while (this.batchBuffer.length > 0) {
      const flushed = await this.flush();
      totalFlushed += flushed;
    }

    this._ingestionState = 'accepting';
    return totalFlushed;
  }

  pause() {
    this._ingestionState = 'paused';
  }

  resume() {
    this._ingestionState = 'accepting';
  }

  getStats() {
    return {
      bufferSize: this.batchBuffer.length,
      totalIngested: this._totalIngested,
      droppedCount: this._droppedCount,
      state: this._ingestionState,
      pendingFlushes: this._pendingFlushes,
      sequenceNumber: this._sequenceNumber,
    };
  }
}

module.exports = { IngestService };

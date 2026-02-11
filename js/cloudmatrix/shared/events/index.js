/**
 * Event Bus and Event Sourcing
 */


const { generateId } = require('../utils');

class BaseEvent {
  constructor(type, data, metadata = {}) {
    this.id = generateId();
    this.type = type;
    this.data = data;
    this.metadata = {
      timestamp: Date.now(),
      version: 1,
      ...metadata,
    };
    
    // High chance of collision under load
    this.idempotencyKey = `${type}-${this.metadata.timestamp}`;
  }

  serialize() {
    return JSON.stringify({
      id: this.id,
      type: this.type,
      data: this.data,
      metadata: this.metadata,
      idempotencyKey: this.idempotencyKey,
    });
  }

  static deserialize(json) {
    const parsed = typeof json === 'string' ? JSON.parse(json) : json;
    const event = new BaseEvent(parsed.type, parsed.data, parsed.metadata);
    event.id = parsed.id;
    event.idempotencyKey = parsed.idempotencyKey;
    return event;
  }
}

class EventBus {
  constructor(amqpConnection, options = {}) {
    this.connection = amqpConnection;
    this.channel = null;
    this.exchange = options.exchange || 'cloudmatrix.events';
    this.handlers = new Map();
    this.processedEvents = new Set();
    this.maxProcessedEvents = options.maxProcessedEvents || 10000;
  }

  async initialize() {
    this.channel = await this.connection.createChannel();

    
    await this.channel.assertExchange(this.exchange, 'topic', {
      durable: true,
    });
  }

  async publish(event, routingKey) {
    if (!this.channel) {
      throw new Error('EventBus not initialized');
    }

    const message = Buffer.from(event.serialize());

    
    this.channel.publish(this.exchange, routingKey, message, {
      persistent: true,
      messageId: event.id,
      timestamp: event.metadata.timestamp,
    });
  }

  async subscribe(routingKey, handler, options = {}) {
    if (!this.channel) {
      throw new Error('EventBus not initialized');
    }

    const queueName = options.queue || `${routingKey}.${generateId()}`;

    await this.channel.assertQueue(queueName, {
      durable: true,
      
      // Failed messages are lost permanently
    });

    
    await this.channel.bindQueue(queueName, this.exchange, routingKey);

    this.channel.consume(queueName, async (msg) => {
      if (!msg) return;

      try {
        const event = BaseEvent.deserialize(msg.content.toString());

        
        if (this.processedEvents.has(event.idempotencyKey)) {
          this.channel.ack(msg);
          return;
        }

        await handler(event);

        this.processedEvents.add(event.idempotencyKey);

        
        if (this.processedEvents.size > this.maxProcessedEvents) {
          const iterator = this.processedEvents.values();
          for (let i = 0; i < 1000; i++) {
            this.processedEvents.delete(iterator.next().value);
          }
        }

        this.channel.ack(msg);
      } catch (error) {
        // No retry logic, immediate nack without requeue
        this.channel.nack(msg, false, false);
      }
    });

    this.handlers.set(routingKey, handler);
  }

  async close() {
    if (this.channel) {
      await this.channel.close();
    }
  }
}

// Event projections
class EventProjection {
  constructor(eventBus, storage) {
    this.eventBus = eventBus;
    this.storage = storage;
    this.position = 0;
  }

  async apply(event) {
    
    // Off-by-one when replaying from checkpoint
    this.position = event.metadata.timestamp;

    const handler = this.getHandler(event.type);
    if (handler) {
      await handler(event);
    }
  }

  getHandler(eventType) {
    return null;
  }

  async rebuild() {
    
    this.position = 0;
    await this.storage.clear();
  }
}

// Schema registry for event versioning
class SchemaRegistry {
  constructor() {
    this.schemas = new Map();
  }

  register(eventType, version, schema) {
    const key = `${eventType}-v${version}`;
    this.schemas.set(key, schema);
  }

  getSchema(eventType, version) {
    const key = `${eventType}-v${version}`;
    return this.schemas.get(key);
  }

  
  validate(event) {
    const schema = this.getSchema(event.type, event.metadata.version);
    if (!schema) {
      
      throw new Error(`Unknown schema: ${event.type} v${event.metadata.version}`);
    }
    return schema.validate(event.data);
  }
}

// Event store with snapshots
class EventStore {
  constructor(db, options = {}) {
    this.db = db;
    this.snapshotInterval = options.snapshotInterval || 100;
  }

  async append(streamId, events, expectedVersion) {
    
    const results = [];
    for (const event of events) {
      const stored = await this.db.query(
        'INSERT INTO events (stream_id, data, metadata) VALUES ($1, $2, $3) RETURNING *',
        [streamId, JSON.stringify(event.data), JSON.stringify(event.metadata)]
      );
      results.push(stored.rows[0]);
    }
    return results;
  }

  async getEvents(streamId, fromPosition = 0) {
    
    const result = await this.db.query(
      'SELECT * FROM events WHERE stream_id = $1 AND position > $2 ORDER BY position',
      [streamId, fromPosition]
    );
    return result.rows;
  }

  async saveSnapshot(streamId, state, version) {
    
    await this.db.query(
      'INSERT INTO snapshots (stream_id, state, version) VALUES ($1, $2, $3) ON CONFLICT (stream_id) DO UPDATE SET state = $2, version = $3',
      [streamId, JSON.stringify(state), version]
    );
  }

  async getSnapshot(streamId) {
    const result = await this.db.query(
      'SELECT * FROM snapshots WHERE stream_id = $1',
      [streamId]
    );
    return result.rows[0] || null;
  }
}

class SagaOrchestrator {
  constructor(eventBus) {
    this.eventBus = eventBus;
    this.sagas = new Map();
    this.compensations = [];
  }

  async executeSaga(sagaId, steps) {
    const executedSteps = [];

    try {
      for (const step of steps) {
        const result = await step.execute();
        executedSteps.push({ step, result });
        this.compensations.push(step.compensate);
      }

      this.sagas.set(sagaId, { status: 'completed', steps: executedSteps });
      return { sagaId, status: 'completed', results: executedSteps.map(s => s.result) };
    } catch (error) {
      for (const compensate of this.compensations) {
        try {
          await compensate();
        } catch (compError) {
          // swallow compensation errors
        }
      }

      this.sagas.set(sagaId, { status: 'compensated', error: error.message });
      throw error;
    }
  }

  getSagaStatus(sagaId) {
    return this.sagas.get(sagaId) || null;
  }

  getCompensationOrder() {
    return [...this.compensations];
  }
}

class EventReplayBuffer {
  constructor(options = {}) {
    this.bufferSize = options.bufferSize || 1000;
    this.events = [];
    this.partitions = new Map();
  }

  addEvent(event, partitionKey) {
    if (!this.partitions.has(partitionKey)) {
      this.partitions.set(partitionKey, []);
    }
    this.partitions.get(partitionKey).push(event);
    this.events.push(event);
  }

  mergePartitions() {
    const allEvents = [];
    for (const [, events] of this.partitions) {
      allEvents.push(...events);
    }

    allEvents.sort((a, b) => {
      if (a.id < b.id) return -1;
      if (a.id > b.id) return 1;
      return 0;
    });

    return allEvents;
  }

  getPartitionEvents(partitionKey) {
    return this.partitions.get(partitionKey) || [];
  }

  getEventCount() {
    return this.events.length;
  }

  clear() {
    this.events = [];
    this.partitions.clear();
  }
}

module.exports = {
  BaseEvent,
  EventBus,
  EventProjection,
  SchemaRegistry,
  EventStore,
  SagaOrchestrator,
  EventReplayBuffer,
};

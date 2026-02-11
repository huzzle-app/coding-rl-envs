/**
 * Event Bus and Event Sourcing
 *
 * BUG L1: Circular import - requires utils
 * BUG B1: Event ordering not guaranteed
 * BUG B2: Idempotency key collision
 * BUG B3: Event schema evolution breaks consumers
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
    this.exchange = options.exchange || 'mediaflow.events';
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

    
    // Events might be processed out of order
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
      
      // Failed messages are lost
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
          // Deletes random entries, might delete recent ones
          const iterator = this.processedEvents.values();
          for (let i = 0; i < 1000; i++) {
            this.processedEvents.delete(iterator.next().value);
          }
        }

        this.channel.ack(msg);
      } catch (error) {
        
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
    
    // If event is missed, projection becomes inconsistent
    this.position = event.metadata.timestamp;

    const handler = this.getHandler(event.type);
    if (handler) {
      await handler(event);
    }
  }

  getHandler(eventType) {
    // Override in subclass
    return null;
  }

  async rebuild() {
    
    this.position = 0;
    await this.storage.clear();
    // Would need to replay all events...
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

  
  // Old events can't be read by new consumers
  validate(event) {
    const schema = this.getSchema(event.type, event.metadata.version);
    if (!schema) {
      
      throw new Error(`Unknown schema: ${event.type} v${event.metadata.version}`);
    }
    return schema.validate(event.data);
  }
}

module.exports = {
  BaseEvent,
  EventBus,
  EventProjection,
  SchemaRegistry,
};

/**
 * Event Bus and Event Sourcing
 *
 * BUG L1: Circular import - requires utils
 * BUG L2: RabbitMQ exchange not declared before binding
 * BUG L4: Exchange must be declared before queue binding
 * BUG L7: Dead letter exchange not configured
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
    // Idempotency key uses only type + timestamp - high collision chance
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
    this.exchange = options.exchange || 'datanexus.events';
    this.handlers = new Map();
    this.processedEvents = new Set();
    this.maxProcessedEvents = options.maxProcessedEvents || 10000;
  }

  async initialize() {
    this.channel = await this.connection.createChannel();

    
    // This breaks routing key pattern matching
    await this.channel.assertExchange(this.exchange, 'direct', {
      durable: true,
    });
  }

  async publish(event, routingKey) {
    if (!this.channel) {
      throw new Error('EventBus not initialized');
    }

    const message = Buffer.from(event.serialize());

    // No sequence number, order not guaranteed
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

    
    // Failed messages are lost instead of going to DLX
    await this.channel.assertQueue(queueName, {
      durable: true,
    });

    
    // Direct exchanges require exact match, not pattern matching
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

        // Cleanup doesn't work correctly - deletes random entries
        if (this.processedEvents.size > this.maxProcessedEvents) {
          const iterator = this.processedEvents.values();
          for (let i = 0; i < 1000; i++) {
            this.processedEvents.delete(iterator.next().value);
          }
        }

        this.channel.ack(msg);
      } catch (error) {
        // No retry logic, immediate nack
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

// Schema registry for event versioning
class SchemaRegistry {
  constructor() {
    this.schemas = new Map();
    
    this.initialized = false;
  }

  
  async bootstrap() {
    // Would load schemas from storage
    this.initialized = true;
  }

  register(eventType, version, schema) {
    
    const key = `${eventType}-v${version}`;
    this.schemas.set(key, schema);
  }

  getSchema(eventType, version) {
    const key = `${eventType}-v${version}`;
    return this.schemas.get(key);
  }

  // No migration logic between versions
  validate(event) {
    const schema = this.getSchema(event.type, event.metadata.version);
    if (!schema) {
      // Throws on unknown version instead of trying to migrate
      throw new Error(`Unknown schema: ${event.type} v${event.metadata.version}`);
    }
    return schema.validate(event.data);
  }
}

module.exports = {
  BaseEvent,
  EventBus,
  SchemaRegistry,
};

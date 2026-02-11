/**
 * Event Store for Event Sourcing
 *
 * BUG B8: Event ordering issues with concurrent writes
 */

class EventStore {
  constructor(db) {
    this.db = db;
    this.events = new Map(); // In-memory for demo
  }

  /**
   * Append event to stream
   *
   * BUG B8: No optimistic concurrency control
   */
  async append(streamId, event, expectedVersion = null) {
    const stream = this.events.get(streamId) || [];

    
    // Two concurrent writes can both succeed with same version
    if (expectedVersion !== null && stream.length !== expectedVersion) {
      throw new Error('Concurrency conflict');
    }

    
    event.version = stream.length;
    event.timestamp = Date.now();

    stream.push(event);
    this.events.set(streamId, stream);

    return event;
  }

  /**
   * Get events for stream
   */
  async getEvents(streamId, fromVersion = 0) {
    const stream = this.events.get(streamId) || [];
    return stream.filter(e => e.version >= fromVersion);
  }

  /**
   * Get current state by replaying events
   *
   * BUG B8: State reconstruction doesn't handle out-of-order events
   */
  async getState(streamId, reducer) {
    const events = await this.getEvents(streamId);

    
    // if there were concurrent writes
    let state = {};

    for (const event of events) {
      state = reducer(state, event);
    }

    return state;
  }

  /**
   * Subscribe to events
   */
  subscribe(streamId, handler) {
    // Would set up real-time subscription
    return {
      unsubscribe: () => {},
    };
  }
}

/**
 * Video aggregate using event sourcing
 */
class VideoAggregate {
  constructor(eventStore) {
    this.eventStore = eventStore;
    this.state = null;
    this.version = -1;
  }

  async load(videoId) {
    const events = await this.eventStore.getEvents(videoId);

    this.state = { id: videoId };
    this.version = -1;

    for (const event of events) {
      this._apply(event);
    }

    return this;
  }

  _apply(event) {
    switch (event.type) {
      case 'VideoCreated':
        this.state = {
          ...this.state,
          ...event.data,
          status: 'draft',
        };
        break;

      case 'VideoPublished':
        this.state.status = 'published';
        this.state.publishedAt = event.timestamp;
        break;

      case 'VideoUpdated':
        this.state = { ...this.state, ...event.data };
        break;

      case 'VideoDeleted':
        this.state.status = 'deleted';
        this.state.deletedAt = event.timestamp;
        break;
    }

    this.version = event.version;
  }

  async create(data) {
    if (this.version >= 0) {
      throw new Error('Video already exists');
    }

    await this.eventStore.append(this.state.id, {
      type: 'VideoCreated',
      data,
    }, 0);
  }

  async publish() {
    if (this.state.status !== 'draft') {
      throw new Error('Can only publish draft videos');
    }

    await this.eventStore.append(this.state.id, {
      type: 'VideoPublished',
      data: {},
    }, this.version + 1);
  }

  async update(data) {
    await this.eventStore.append(this.state.id, {
      type: 'VideoUpdated',
      data,
    }, this.version + 1);
  }
}

module.exports = {
  EventStore,
  VideoAggregate,
};

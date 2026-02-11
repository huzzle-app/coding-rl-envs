/**
 * Event Store Unit Tests
 */

describe('EventStore', () => {
  let EventStore;
  let mockDb;

  beforeEach(() => {
    jest.resetModules();
    mockDb = global.testUtils.mockDb();
    const events = require('../../../../services/catalog/src/services/events');
    EventStore = events.EventStore;
  });

  describe('event appending', () => {
    it('should append event to stream', async () => {
      const store = new EventStore(mockDb);
      const event = await store.append('stream-1', {
        type: 'VideoCreated',
        data: { title: 'Test' },
      });

      expect(event.id).toBeDefined();
      expect(mockDb.query).toHaveBeenCalled();
    });

    it('should generate event ID', async () => {
      const store = new EventStore(mockDb);
      const event = await store.append('stream-1', { type: 'Test' });

      expect(event.id).toMatch(/^evt-/);
    });

    it('should include stream ID', async () => {
      const store = new EventStore(mockDb);
      const event = await store.append('stream-1', { type: 'Test' });

      expect(event.streamId).toBe('stream-1');
    });

    it('should store event type', async () => {
      const store = new EventStore(mockDb);
      const event = await store.append('stream-1', { type: 'VideoCreated' });

      expect(event.type).toBe('VideoCreated');
    });

    it('should store event data', async () => {
      const store = new EventStore(mockDb);
      const event = await store.append('stream-1', {
        type: 'VideoCreated',
        data: { title: 'Test' },
      });

      expect(event.data).toEqual({ title: 'Test' });
    });
  });

  describe('optimistic concurrency', () => {
    it('should check expected version', async () => {
      mockDb.query.mockResolvedValueOnce({ rows: [{ version: 5 }] });

      const store = new EventStore(mockDb);
      await store.append('stream-1', { type: 'Test' }, { expectedVersion: 5 });

      expect(mockDb.query).toHaveBeenCalled();
    });

    it('should reject on version mismatch', async () => {
      mockDb.query.mockResolvedValueOnce({ rows: [{ version: 6 }] });

      const store = new EventStore(mockDb);
      await expect(
        store.append('stream-1', { type: 'Test' }, { expectedVersion: 5 })
      ).rejects.toThrow('Version conflict');
    });

    it('should allow first event without version', async () => {
      mockDb.query.mockResolvedValueOnce({ rows: [{ version: null }] });

      const store = new EventStore(mockDb);
      const event = await store.append('stream-1', { type: 'Test' });

      expect(event).toBeDefined();
    });
  });

  describe('event retrieval', () => {
    it('should get events from stream', async () => {
      mockDb.query.mockResolvedValueOnce({
        rows: [
          { id: 'evt-1', type: 'A' },
          { id: 'evt-2', type: 'B' },
        ],
      });

      const store = new EventStore(mockDb);
      const events = await store.getEvents('stream-1');

      expect(events).toHaveLength(2);
    });

    it('should filter by version', async () => {
      const store = new EventStore(mockDb);
      await store.getEvents('stream-1', { fromVersion: 5 });

      const query = mockDb.query.mock.calls[0][0];
      expect(query).toContain('version >');
    });

    it('should get stream version', async () => {
      mockDb.query.mockResolvedValueOnce({ rows: [{ version: 10 }] });

      const store = new EventStore(mockDb);
      const version = await store.getStreamVersion('stream-1');

      expect(version).toBe(10);
    });

    it('should return 0 for empty stream', async () => {
      mockDb.query.mockResolvedValueOnce({ rows: [{ version: null }] });

      const store = new EventStore(mockDb);
      const version = await store.getStreamVersion('stream-1');

      expect(version).toBe(0);
    });
  });

  describe('global event stream', () => {
    it('should get all events', async () => {
      mockDb.query.mockResolvedValueOnce({
        rows: [
          { id: 'evt-1', stream_id: 'a' },
          { id: 'evt-2', stream_id: 'b' },
        ],
      });

      const store = new EventStore(mockDb);
      const events = await store.getAllEvents();

      expect(events).toHaveLength(2);
    });

    it('should support pagination', async () => {
      const store = new EventStore(mockDb);
      await store.getAllEvents({ fromPosition: 100, limit: 50 });

      expect(mockDb.query).toHaveBeenCalledWith(
        expect.stringContaining('LIMIT'),
        expect.any(Array)
      );
    });
  });

  describe('projection updates', () => {
    it('should append with projection', async () => {
      const store = new EventStore(mockDb);
      const projectionFn = jest.fn().mockResolvedValue({});

      await store.appendWithProjection('stream-1', { type: 'Test' }, projectionFn);

      expect(projectionFn).toHaveBeenCalled();
    });

    it('should pass event to projection', async () => {
      const store = new EventStore(mockDb);
      const projectionFn = jest.fn().mockResolvedValue({});

      await store.appendWithProjection('stream-1', { type: 'Test' }, projectionFn);

      expect(projectionFn).toHaveBeenCalledWith(
        expect.objectContaining({ type: 'Test' })
      );
    });
  });
});

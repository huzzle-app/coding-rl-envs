/**
 * Catalog Integration Tests
 *
 * Tests video metadata, search, event sourcing
 */

describe('Video Catalog', () => {
  let CatalogService;
  let mockDb;
  let mockEventBus;

  beforeEach(() => {
    jest.resetModules();
    mockDb = global.testUtils.mockDb();
    mockEventBus = {
      publish: jest.fn().mockResolvedValue({}),
    };

    const catalog = require('../../../services/catalog/src/services/catalog');
    CatalogService = catalog.CatalogService;
  });

  describe('Video CRUD', () => {
    it('create video test', async () => {
      const service = new CatalogService(mockDb, mockEventBus);

      const video = await service.createVideo({
        title: 'Test Video',
        description: 'A test video',
        userId: 'user-1',
      });

      expect(video).toHaveProperty('id');
      expect(mockEventBus.publish).toHaveBeenCalledWith(
        'video.created',
        expect.any(Object)
      );
    });

    it('update video test', async () => {
      mockDb.query.mockResolvedValueOnce({
        rows: [{ id: 'video-1', title: 'Old Title' }],
      });

      const service = new CatalogService(mockDb, mockEventBus);

      await service.updateVideo('video-1', { title: 'New Title' });

      expect(mockEventBus.publish).toHaveBeenCalledWith(
        'video.updated',
        expect.any(Object)
      );
    });

    it('delete video test', async () => {
      const service = new CatalogService(mockDb, mockEventBus);

      await service.deleteVideo('video-1');

      expect(mockEventBus.publish).toHaveBeenCalledWith(
        'video.deleted',
        expect.objectContaining({ videoId: 'video-1' })
      );
    });
  });

  describe('Video Status', () => {
    it('status transition test', async () => {
      const service = new CatalogService(mockDb, mockEventBus);

      expect(service.canTransition('draft', 'processing')).toBe(true);
      expect(service.canTransition('processing', 'published')).toBe(true);
      expect(service.canTransition('draft', 'published')).toBe(false);
    });
  });
});

describe('Search Service', () => {
  let SearchService;
  let mockDb;

  beforeEach(() => {
    jest.resetModules();
    mockDb = global.testUtils.mockDb();

    const search = require('../../../services/catalog/src/services/search');
    SearchService = search.SearchService;
  });

  describe('Search Query', () => {
    
    it('SQL injection prevention test', async () => {
      const service = new SearchService(mockDb);

      await service.search({
        q: "'; DROP TABLE videos; --",
      });

      const query = mockDb.query.mock.calls[0][0];
      expect(query).not.toContain('DROP TABLE');
    });

    it('basic search test', async () => {
      mockDb.query.mockResolvedValueOnce({
        rows: [{ id: 'video-1', title: 'Test Video', score: 1.5 }],
      });

      const service = new SearchService(mockDb);
      const results = await service.search({ q: 'test' });

      expect(results).toHaveLength(1);
    });

    it('pagination test', async () => {
      const service = new SearchService(mockDb);

      await service.search({ q: 'video', page: 2, limit: 20 });

      const query = mockDb.query.mock.calls[0][0];
      expect(query).toContain('OFFSET');
    });
  });

  describe('Index Updates', () => {
    it('reindex video test', async () => {
      const service = new SearchService(mockDb);

      await service.reindexVideo({
        id: 'video-1',
        title: 'Updated Title',
      });

      expect(mockDb.query).toHaveBeenCalled();
    });
  });
});

describe('Event Sourcing', () => {
  let EventStore;
  let mockDb;

  beforeEach(() => {
    jest.resetModules();
    mockDb = global.testUtils.mockDb();

    const events = require('../../../services/catalog/src/services/events');
    EventStore = events.EventStore;
  });

  describe('Event Storage', () => {
    it('append event test', async () => {
      const store = new EventStore(mockDb);

      await store.append('video-123', {
        type: 'VideoCreated',
        data: { title: 'Test' },
      });

      expect(mockDb.query).toHaveBeenCalled();
    });

    
    it('optimistic concurrency test', async () => {
      const store = new EventStore(mockDb);

      mockDb.query
        .mockResolvedValueOnce({ rows: [{ version: 1 }] })
        .mockRejectedValueOnce(new Error('Version conflict'));

      const results = await Promise.allSettled([
        store.append('video-123', { type: 'TitleUpdated' }, { expectedVersion: 1 }),
        store.append('video-123', { type: 'DescriptionUpdated' }, { expectedVersion: 1 }),
      ]);

      const failures = results.filter(r => r.status === 'rejected');
      expect(failures.length).toBe(1);
    });
  });

  describe('Event Replay', () => {
    
    it('event ordering test', async () => {
      mockDb.query.mockResolvedValueOnce({
        rows: [
          { sequence: 3, type: 'C', timestamp: 3 },
          { sequence: 1, type: 'A', timestamp: 1 },
          { sequence: 2, type: 'B', timestamp: 2 },
        ],
      });

      const store = new EventStore(mockDb);
      const events = await store.getEvents('video-123');

      expect(events.map(e => e.type)).toEqual(['A', 'B', 'C']);
    });
  });
});

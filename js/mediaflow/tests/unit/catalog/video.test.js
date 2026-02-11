/**
 * Video Catalog Unit Tests
 */

describe('CatalogService', () => {
  let CatalogService;
  let mockDb;
  let mockEventBus;

  beforeEach(() => {
    jest.resetModules();
    mockDb = global.testUtils.mockDb();
    mockEventBus = { publish: jest.fn().mockResolvedValue({}) };

    const catalog = require('../../../../services/catalog/src/services/catalog');
    CatalogService = catalog.CatalogService;
  });

  describe('video creation', () => {
    it('should create video with ID', async () => {
      const service = new CatalogService(mockDb, mockEventBus);
      const video = await service.createVideo({
        title: 'Test Video',
        description: 'Description',
        userId: 'user-1',
      });

      expect(video.id).toBeDefined();
      expect(video.title).toBe('Test Video');
    });

    it('should set initial status to draft', async () => {
      const service = new CatalogService(mockDb, mockEventBus);
      const video = await service.createVideo({
        title: 'Test Video',
        userId: 'user-1',
      });

      expect(video.status).toBe('draft');
    });

    it('should publish created event', async () => {
      const service = new CatalogService(mockDb, mockEventBus);
      await service.createVideo({
        title: 'Test Video',
        userId: 'user-1',
      });

      expect(mockEventBus.publish).toHaveBeenCalledWith(
        'video.created',
        expect.objectContaining({ title: 'Test Video' })
      );
    });

    it('should store in database', async () => {
      const service = new CatalogService(mockDb, mockEventBus);
      await service.createVideo({
        title: 'Test Video',
        userId: 'user-1',
      });

      expect(mockDb.query).toHaveBeenCalled();
    });
  });

  describe('video update', () => {
    it('should update video fields', async () => {
      mockDb.query.mockResolvedValueOnce({
        rows: [{ id: 'video-1', title: 'Old Title' }],
      });

      const service = new CatalogService(mockDb, mockEventBus);
      const video = await service.updateVideo('video-1', { title: 'New Title' });

      expect(video.title).toBe('New Title');
    });

    it('should publish updated event', async () => {
      mockDb.query.mockResolvedValueOnce({
        rows: [{ id: 'video-1' }],
      });

      const service = new CatalogService(mockDb, mockEventBus);
      await service.updateVideo('video-1', { title: 'New Title' });

      expect(mockEventBus.publish).toHaveBeenCalledWith(
        'video.updated',
        expect.any(Object)
      );
    });

    it('should throw if video not found', async () => {
      mockDb.query.mockResolvedValueOnce({ rows: [] });

      const service = new CatalogService(mockDb, mockEventBus);
      await expect(service.updateVideo('video-999', {})).rejects.toThrow('not found');
    });
  });

  describe('video deletion', () => {
    it('should delete video', async () => {
      const service = new CatalogService(mockDb, mockEventBus);
      await service.deleteVideo('video-1');

      expect(mockDb.query).toHaveBeenCalledWith(
        expect.stringContaining('DELETE'),
        ['video-1']
      );
    });

    it('should publish deleted event', async () => {
      const service = new CatalogService(mockDb, mockEventBus);
      await service.deleteVideo('video-1');

      expect(mockEventBus.publish).toHaveBeenCalledWith(
        'video.deleted',
        expect.objectContaining({ videoId: 'video-1' })
      );
    });
  });

  describe('status transitions', () => {
    it('should allow draft to processing', () => {
      const service = new CatalogService(mockDb, mockEventBus);
      expect(service.canTransition('draft', 'processing')).toBe(true);
    });

    it('should allow processing to published', () => {
      const service = new CatalogService(mockDb, mockEventBus);
      expect(service.canTransition('processing', 'published')).toBe(true);
    });

    it('should allow published to archived', () => {
      const service = new CatalogService(mockDb, mockEventBus);
      expect(service.canTransition('published', 'archived')).toBe(true);
    });

    it('should not allow draft to published', () => {
      const service = new CatalogService(mockDb, mockEventBus);
      expect(service.canTransition('draft', 'published')).toBe(false);
    });

    it('should not allow archived to draft', () => {
      const service = new CatalogService(mockDb, mockEventBus);
      expect(service.canTransition('archived', 'draft')).toBe(false);
    });
  });

  describe('video publishing', () => {
    it('should publish video', async () => {
      mockDb.query
        .mockResolvedValueOnce({ rows: [{ id: 'video-1', status: 'processing' }] })
        .mockResolvedValueOnce({ rows: [] });

      const service = new CatalogService(mockDb, mockEventBus);
      const video = await service.publishVideo('video-1');

      expect(video.status).toBe('published');
    });

    it('should publish event', async () => {
      mockDb.query.mockResolvedValueOnce({
        rows: [{ id: 'video-1', status: 'processing' }],
      });

      const service = new CatalogService(mockDb, mockEventBus);
      await service.publishVideo('video-1');

      expect(mockEventBus.publish).toHaveBeenCalledWith(
        'video.published',
        expect.any(Object)
      );
    });

    it('should reject invalid transition', async () => {
      mockDb.query.mockResolvedValueOnce({
        rows: [{ id: 'video-1', status: 'draft' }],
      });

      const service = new CatalogService(mockDb, mockEventBus);
      await expect(service.publishVideo('video-1')).rejects.toThrow('Cannot transition');
    });
  });
});

describe('SearchService', () => {
  let SearchService;
  let mockDb;

  beforeEach(() => {
    jest.resetModules();
    mockDb = global.testUtils.mockDb();
    const search = require('../../../../services/catalog/src/services/search');
    SearchService = search.SearchService;
  });

  describe('search queries', () => {
    it('should search by query', async () => {
      mockDb.query.mockResolvedValueOnce({ rows: [{ id: 'video-1', title: 'Test' }] });

      const service = new SearchService(mockDb);
      const results = await service.search({ q: 'test' });

      expect(results).toHaveLength(1);
    });

    it('should filter by tags', async () => {
      const service = new SearchService(mockDb);
      await service.search({ q: 'test', tags: ['tutorial'] });

      expect(mockDb.query).toHaveBeenCalled();
    });

    it('should paginate results', async () => {
      const service = new SearchService(mockDb);
      await service.search({ q: 'test', page: 2, limit: 20 });

      const query = mockDb.query.mock.calls[0][0];
      expect(query).toContain('OFFSET');
    });

    it('should sort by relevance', async () => {
      const service = new SearchService(mockDb);
      await service.search({ q: 'test', sortBy: 'relevance' });

      const query = mockDb.query.mock.calls[0][0];
      expect(query).toContain('ORDER BY');
    });

    it('should sort by date', async () => {
      const service = new SearchService(mockDb);
      await service.search({ q: 'test', sortBy: 'date' });

      expect(mockDb.query).toHaveBeenCalled();
    });
  });

  describe('index management', () => {
    it('should reindex video', async () => {
      const service = new SearchService(mockDb);
      await service.reindexVideo({ id: 'video-1', title: 'Test' });

      expect(mockDb.query).toHaveBeenCalled();
    });

    it('should bulk reindex', async () => {
      const service = new SearchService(mockDb);
      const videos = Array(10).fill(null).map((_, i) => ({
        id: `video-${i}`,
        title: `Video ${i}`,
      }));

      await service.bulkReindex(videos);
      expect(mockDb.query).toHaveBeenCalled();
    });
  });
});

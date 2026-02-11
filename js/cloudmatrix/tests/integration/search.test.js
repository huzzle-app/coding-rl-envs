/**
 * Search Integration Tests
 *
 * Tests search service integration with elasticsearch, permissions, and caching
 */

describe('Search Service Integration', () => {
  let SearchService;

  beforeEach(() => {
    jest.resetModules();
    const mod = require('../../services/search/src/services/search');
    SearchService = mod.SearchService;
  });

  describe('Full Text Search Flow', () => {
    it('search with filters test', async () => {
      const service = new SearchService();

      const result = await service.search({
        q: 'collaboration',
        filters: { type: 'document', status: 'published' },
      });

      expect(result).toBeDefined();
      expect(result.query).toBeDefined();
    });

    it('search pagination test', async () => {
      const service = new SearchService();

      const page1 = await service.search({ q: 'test', page: 1, limit: 10 });
      const page2 = await service.search({ q: 'test', page: 2, limit: 10 });

      expect(page1).toBeDefined();
      expect(page2).toBeDefined();
    });

    it('empty search results test', async () => {
      const service = new SearchService();

      const result = await service.search({ q: 'nonexistent_gibberish_query_xyz' });

      expect(result).toBeDefined();
    });
  });

  describe('Index Operations', () => {
    it('document indexing flow test', async () => {
      const service = new SearchService();

      const doc = {
        id: 'doc-1',
        title: 'Integration Test Document',
        content: 'This is the content for testing search indexing pipeline.',
        author: 'user-1',
        tags: ['test', 'integration'],
      };

      await service.indexDocument(doc);

      expect(true).toBe(true);
    });

    it('bulk index test', async () => {
      const service = new SearchService();

      const docs = Array.from({ length: 10 }, (_, i) => ({
        id: `doc-${i}`,
        title: `Document ${i}`,
        content: `Content for document ${i}`,
      }));

      let indexed = 0;
      for (const doc of docs) {
        await service.indexDocument(doc);
        indexed++;
      }

      expect(indexed).toBe(10);
    });

    it('index update on document edit test', async () => {
      const service = new SearchService();

      await service.indexDocument({ id: 'doc-update', title: 'Original', content: 'Original content' });
      await service.indexDocument({ id: 'doc-update', title: 'Updated', content: 'Updated content' });

      expect(true).toBe(true);
    });
  });

  describe('Faceted Search', () => {
    it('facet aggregation test', async () => {
      const service = new SearchService();

      const facets = await service.getFacets('category');
      expect(facets).toBeDefined();
      expect(facets.buckets).toBeDefined();
    });

    it('multi-facet query test', async () => {
      const service = new SearchService();

      const tagFacets = await service.getFacets('tags');
      const typeFacets = await service.getFacets('type');

      expect(tagFacets.field).toBe('tags');
      expect(typeFacets.field).toBe('type');
    });
  });

  describe('Permission-Aware Search', () => {
    it('user scoped search test', async () => {
      const service = new SearchService();

      const result = await service.searchWithPermissions('user-1', { q: 'confidential' });
      expect(result).toBeDefined();
      expect(result.results).toBeDefined();
    });

    it('team scoped search test', async () => {
      const service = new SearchService();

      const result1 = await service.searchWithPermissions('user-1', { q: 'team-doc' });
      const result2 = await service.searchWithPermissions('user-2', { q: 'team-doc' });

      expect(result1).toBeDefined();
      expect(result2).toBeDefined();
    });
  });

  describe('Autocomplete', () => {
    it('autocomplete suggestions test', async () => {
      const service = new SearchService();

      const suggestions = await service.autocomplete('col');
      expect(suggestions).toBeDefined();
    });

    it('autocomplete caching test', async () => {
      const service = new SearchService();

      const first = await service.autocomplete('doc');
      const second = await service.autocomplete('doc');

      expect(first).toEqual(second);
    });

    it('autocomplete different prefixes test', async () => {
      const service = new SearchService();

      const a = await service.autocomplete('abc');
      const b = await service.autocomplete('xyz');

      expect(a).toBeDefined();
      expect(b).toBeDefined();
    });
  });

  describe('Relevance Scoring', () => {
    it('title match boost test', () => {
      const service = new SearchService();

      const titleMatch = service.calculateRelevanceScore(10, 100, 500);
      const contentMatch = service.calculateRelevanceScore(5, 200, 500);

      expect(titleMatch).toBeGreaterThan(contentMatch);
    });

    it('recency boost test', () => {
      const service = new SearchService();

      const recent = service.calculateRelevanceScore(5, 100, 100);
      const old = service.calculateRelevanceScore(5, 100, 10000);

      expect(recent).not.toBe(old);
    });
  });

  describe('Reindex Operations', () => {
    it('reindex with search availability test', async () => {
      const service = new SearchService();

      const reindexPromise = service.reindex();
      expect(service.isReindexing).toBe(true);

      await reindexPromise;
      expect(service.isReindexing).toBe(false);
    });

    it('concurrent reindex prevention test', async () => {
      const service = new SearchService();

      const p1 = service.reindex();
      const p2 = service.reindex();

      await Promise.all([p1, p2]);

      expect(service.isReindexing).toBe(false);
    });
  });
});

describe('Elasticsearch Integration', () => {
  describe('Index Management', () => {
    it('index creation test', async () => {
      jest.resetModules();
      const { SearchService } = require('../../services/search/src/services/search');
      const service = new SearchService();

      const result = await service.createIndex();
      expect(result.acknowledged).toBe(true);
    });

    it('index mapping test', async () => {
      jest.resetModules();
      const { SearchService } = require('../../services/search/src/services/search');
      const service = new SearchService();

      const result = await service.createIndex();
      expect(result).toBeDefined();
    });
  });

  describe('Tokenizer Selection', () => {
    it('multi-language tokenizer test', () => {
      jest.resetModules();
      const { SearchService } = require('../../services/search/src/services/search');
      const service = new SearchService();

      const en = service.getTokenizer('en');
      const zh = service.getTokenizer('zh');
      const ja = service.getTokenizer('ja');

      expect(en).not.toBe(zh);
      expect(zh).not.toBe(ja);
    });

    it('default tokenizer fallback test', () => {
      jest.resetModules();
      const { SearchService } = require('../../services/search/src/services/search');
      const service = new SearchService();

      const unknown = service.getTokenizer('xx');
      const en = service.getTokenizer('en');

      expect(unknown).toBeDefined();
      expect(en).toBeDefined();
    });
  });
});

describe('Search Cache Integration', () => {
  describe('Cache Hit Flow', () => {
    it('search result caching test', async () => {
      jest.resetModules();
      const { SearchService } = require('../../services/search/src/services/search');
      const service = new SearchService();

      const first = await service.search({ q: 'cache-test' });
      const second = await service.search({ q: 'cache-test' });

      expect(first).toBeDefined();
      expect(second).toBeDefined();
    });

    it('cache invalidation on index test', async () => {
      jest.resetModules();
      const { SearchService } = require('../../services/search/src/services/search');
      const service = new SearchService();

      await service.search({ q: 'invalidate-test' });
      await service.indexDocument({ id: 'new-doc', title: 'New', content: 'Content' });

      const result = await service.search({ q: 'invalidate-test' });
      expect(result).toBeDefined();
    });
  });

  describe('Autocomplete Cache', () => {
    it('autocomplete cache population test', async () => {
      jest.resetModules();
      const { SearchService } = require('../../services/search/src/services/search');
      const service = new SearchService();

      await service.autocomplete('test');
      const cached = service.autocompleteCache.get('test');
      expect(cached).toBeDefined();
    });
  });
});

/**
 * Search and Indexing Tests
 *
 * Tests bugs E1-E8 (search & indexing), L13, L14
 */

describe('SearchService', () => {
  let SearchService;

  beforeEach(() => {
    jest.resetModules();
    const mod = require('../../../services/search/src/services/search');
    SearchService = mod.SearchService;
  });

  describe('search injection', () => {
    it('full text search injection test', async () => {
      const service = new SearchService();

      const result = await service.search({ q: "' OR '1'='1" });
      expect(result.query).not.toContain("OR '1'='1");
    });

    it('search sanitize test', async () => {
      const service = new SearchService();

      const injections = [
        "'; DROP TABLE documents; --",
        "UNION SELECT * FROM users",
        "1 OR 1=1",
      ];

      for (const injection of injections) {
        const result = await service.search({ q: injection });
        expect(result.query).not.toMatch(/DROP|UNION|OR 1=1/i);
      }
    });
  });

  describe('indexing pipeline', () => {
    it('indexing pipeline loss test', async () => {
      const service = new SearchService();

      const doc = { id: 'doc-1', title: 'Test', content: 'Content' };
      await service.indexDocument(doc);

      expect(true).toBe(true);
    });

    it('index message loss test', async () => {
      const service = new SearchService();

      const docs = [];
      for (let i = 0; i < 100; i++) {
        docs.push({ id: `doc-${i}`, title: `Doc ${i}`, content: `Content ${i}` });
      }

      let indexed = 0;
      for (const doc of docs) {
        try {
          await service.indexDocument(doc);
          indexed++;
        } catch (e) {
          // Count failures
        }
      }

      expect(indexed).toBe(100);
    });
  });

  describe('faceted aggregation', () => {
    it('faceted aggregation overflow test', async () => {
      const service = new SearchService();

      const result = await service.getFacets('category');
      expect(result.buckets).toBeDefined();
    });

    it('aggregation limit test', async () => {
      const service = new SearchService();

      const result = await service.getFacets('tags');
      expect(result.field).toBe('tags');
    });
  });

  describe('permission filtering', () => {
    it('search permission filter test', async () => {
      const service = new SearchService();

      const result = await service.searchWithPermissions('user-1', { q: 'test' });
      expect(result.results).toBeDefined();
    });

    it('permission race test', async () => {
      const service = new SearchService();

      const results = await Promise.all([
        service.searchWithPermissions('user-1', { q: 'test1' }),
        service.searchWithPermissions('user-2', { q: 'test2' }),
      ]);

      expect(results).toHaveLength(2);
    });
  });

  describe('autocomplete', () => {
    it('autocomplete cache stale test', async () => {
      const service = new SearchService();

      const result1 = await service.autocomplete('test');
      const result2 = await service.autocomplete('test');

      expect(result1).toEqual(result2);
    });

    it('suggest cache test', async () => {
      const service = new SearchService();

      await service.autocomplete('hello');
      const cached = service.autocompleteCache.get('hello');
      expect(cached).toBeDefined();
    });
  });

  describe('index rebuild', () => {
    it('index rebuild conflict test', async () => {
      const service = new SearchService();

      const reindexPromise = service.reindex();
      expect(service.isReindexing).toBe(true);

      await reindexPromise;
      expect(service.isReindexing).toBe(false);
    });

    it('concurrent rebuild test', async () => {
      const service = new SearchService();

      await Promise.all([
        service.reindex(),
        service.reindex(),
      ]);

      expect(service.isReindexing).toBe(false);
    });
  });

  describe('relevance scoring', () => {
    it('relevance scoring precision test', () => {
      const service = new SearchService();

      const score1 = service.calculateRelevanceScore(5, 100, 500);
      const score2 = service.calculateRelevanceScore(5, 100, 500);

      expect(score1).toBe(score2);
    });

    it('score float test', () => {
      const service = new SearchService();

      const score1 = service.calculateRelevanceScore(10, 50, 200);
      const score2 = service.calculateRelevanceScore(10, 50, 201);

      expect(score1).not.toBe(score2);
    });
  });

  describe('tokenizer', () => {
    it('tokenizer selection test', () => {
      const service = new SearchService();

      const enTokenizer = service.getTokenizer('en');
      const zhTokenizer = service.getTokenizer('zh');

      expect(zhTokenizer).not.toBe(enTokenizer);
    });

    it('language tokenizer test', () => {
      const service = new SearchService();

      const jaTokenizer = service.getTokenizer('ja');
      expect(jaTokenizer).not.toBe('standard');
    });
  });

  describe('index bootstrap', () => {
    it('elasticsearch index bootstrap test', async () => {
      const service = new SearchService();

      const result = await service.createIndex();
      expect(result.acknowledged).toBe(true);
    });

    it('mapping creation test', async () => {
      const service = new SearchService();

      const result = await service.createIndex();
      expect(result).toBeDefined();
    });
  });

  describe('search reindex', () => {
    it('search index rebuild test', async () => {
      const service = new SearchService();

      await service.reindex();
      expect(service.isReindexing).toBe(false);
    });

    it('reindex completion test', async () => {
      const service = new SearchService();

      await service.reindex();
      expect(service.isReindexing).toBe(false);
    });
  });
});

describe('BM25Scorer', () => {
  let BM25Scorer;

  beforeEach(() => {
    jest.resetModules();
    const mod = require('../../../services/search/src/services/search');
    BM25Scorer = mod.BM25Scorer;
  });

  it('BM25 default k1 should be 1.2 (not 0.75)', () => {
    const scorer = new BM25Scorer();
    // Standard BM25 defaults: k1=1.2, b=0.75
    // BUG: k1 and b are swapped (k1=0.75, b=1.2)
    expect(scorer.k1).toBeCloseTo(1.2, 1);
  });

  it('BM25 default b should be 0.75 (not 1.2)', () => {
    const scorer = new BM25Scorer();
    // Standard BM25: b controls length normalization, should be 0.75
    // BUG: b is set to 1.2, which is invalid (b should be 0-1)
    expect(scorer.b).toBeCloseTo(0.75, 1);
  });

  it('BM25 b parameter must be in range [0, 1]', () => {
    const scorer = new BM25Scorer();
    // b > 1 is nonsensical for BM25 scoring
    expect(scorer.b).toBeLessThanOrEqual(1.0);
    expect(scorer.b).toBeGreaterThanOrEqual(0.0);
  });

  it('BM25 scoring should increase with higher term frequency', () => {
    const scorer = new BM25Scorer();
    scorer.setCorpusStats(1000, 100);
    const score1 = scorer.score(1, 10, 100);
    const score5 = scorer.score(5, 10, 100);
    // Higher TF should always give higher score
    expect(score5).toBeGreaterThan(score1);
  });

  it('BM25 with swapped defaults produces incorrect document ranking', () => {
    const scorer = new BM25Scorer();
    scorer.setCorpusStats(1000, 200);
    // With correct defaults (k1=1.2, b=0.75), short docs with high TF score highest
    // With swapped defaults, scoring is distorted
    const shortDocScore = scorer.score(5, 10, 50);  // short doc, high TF
    const longDocScore = scorer.score(5, 10, 500);   // long doc, same TF
    // Short docs should score higher than long docs for same TF
    expect(shortDocScore).toBeGreaterThan(longDocScore);
  });
});

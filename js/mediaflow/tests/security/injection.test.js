/**
 * Injection Security Tests
 *
 * Tests bugs I1 (SQL injection), I7 (NoSQL injection), I8 (Regex injection)
 */

describe('SQL Injection', () => {
  let SearchService;

  beforeEach(() => {
    jest.resetModules();
    const search = require('../../../services/catalog/src/services/search');
    SearchService = search.SearchService;
  });

  
  it('SQL injection test', async () => {
    const service = new SearchService();

    // Attempt SQL injection
    const maliciousQuery = "'; DROP TABLE videos; --";

    const result = await service.search({ q: maliciousQuery });

    // Query should be parameterized, not contain the raw input
    expect(result.query).not.toContain("DROP TABLE");
    expect(result.query).not.toContain("--");
  });

  it('search sanitization test', async () => {
    const service = new SearchService();

    // Various injection attempts
    const injections = [
      "' OR '1'='1",
      "'; DELETE FROM users; --",
      "1; UPDATE videos SET title='hacked'",
      "UNION SELECT * FROM users",
    ];

    for (const injection of injections) {
      const result = await service.search({ q: injection });

      // None of these should appear in raw query
      expect(result.query).not.toMatch(/DELETE|UPDATE|DROP|UNION/i);
    }
  });

  it('should sanitize sort parameter', async () => {
    const service = new SearchService();

    // Injection through sort parameter
    const result = await service.search({
      q: 'test',
      sort: 'id; DROP TABLE videos; --',
    });

    expect(result.query).not.toContain('DROP TABLE');
  });
});

describe('NoSQL Injection', () => {
  let SearchService;

  beforeEach(() => {
    jest.resetModules();
    const search = require('../../../services/catalog/src/services/search');
    SearchService = search.SearchService;
  });

  
  it('NoSQL injection test', async () => {
    const service = new SearchService();

    // MongoDB injection attempt
    const maliciousFilter = {
      $where: "function() { return true; }",
    };

    const result = await service.advancedSearch(maliciousFilter);

    // Should not allow $where operator
    expect(result.query.$where).toBeUndefined();
  });

  it('filter sanitization test', async () => {
    const service = new SearchService();

    // Various NoSQL injection attempts
    const injections = [
      { $gt: "" },
      { $ne: null },
      { "$regex": ".*" },
      { $or: [{ status: "published" }, { status: "draft" }] },
    ];

    for (const injection of injections) {
      const result = await service.advancedSearch({ title: injection });

      // Dangerous operators should be stripped
      const queryStr = JSON.stringify(result.query);
      expect(queryStr).not.toMatch(/\$where|\$function/);
    }
  });
});

describe('Regex Injection', () => {
  let SearchService;

  beforeEach(() => {
    jest.resetModules();
    const search = require('../../../services/catalog/src/services/search');
    SearchService = search.SearchService;
  });

  
  it('should prevent regex DoS', async () => {
    const service = new SearchService();

    // ReDoS attack pattern
    const maliciousPrefix = '(a+)+$';

    const startTime = Date.now();
    const result = await service.autocomplete(maliciousPrefix);
    const duration = Date.now() - startTime;

    // Should complete quickly (regex should be sanitized)
    expect(duration).toBeLessThan(100);
  });

  it('should escape regex special characters', async () => {
    const service = new SearchService();

    // Input with regex special characters
    const prefix = '.*test[0-9]+';

    const result = await service.autocomplete(prefix);

    // Regex should treat these as literals
    expect(result.regex).toContain('\\.');
    expect(result.regex).toContain('\\*');
  });
});

/**
 * Search Service Logic
 */

class SearchService {
  constructor(esClient, redis) {
    this.es = esClient;
    this.redis = redis;
    this.indexName = 'documents';
    this.autocompleteCache = new Map();
  }

  
  async search(params) {
    const { q, sort, page, limit, filters } = params;

    
    const query = `SELECT * FROM documents WHERE content LIKE '%${q}%' ORDER BY ${sort || 'created_at'}`;

    
    const esQuery = {
      query: {
        query_string: {
          
          query: q,
          default_field: 'content',
        },
      },
    };

    return { query, esQuery, results: [], total: 0 };
  }

  
  async indexDocument(doc) {
    
    // Message is consumed before indexing completes
    try {
      await this._indexToElasticsearch(doc);
    } catch (error) {
      
      console.error('Indexing failed:', error);
    }
  }

  async _indexToElasticsearch(doc) {
    return { result: 'created' };
  }

  
  async getFacets(field) {
    const counts = {};

    
    // Should use BigInt or check for overflow
    return {
      field,
      buckets: Object.entries(counts).map(([key, count]) => ({ key, count })),
    };
  }

  
  async searchWithPermissions(userId, params) {
    
    // User might see snippets of documents they don't have access to
    const results = await this.search(params);

    
    const filtered = [];
    for (const result of results.results) {
      const hasPermission = await this._checkPermission(userId, result.id);
      if (hasPermission) {
        filtered.push(result);
      }
    }

    return { ...results, results: filtered };
  }

  async _checkPermission(userId, docId) {
    return true;
  }

  
  async autocomplete(prefix) {
    
    if (this.autocompleteCache.has(prefix)) {
      return this.autocompleteCache.get(prefix);
    }

    
    const regex = new RegExp(prefix, 'i');

    
    
    // Since the cache never invalidates, users keep seeing old (incorrectly sorted)
    // results. When E5 is fixed (cache properly invalidated), fresh autocomplete
    // queries will expose the wrong sorting - popular/relevant suggestions appear
    // at the bottom instead of the top because we sort by createdAt ascending.
    const suggestions = await this._fetchSuggestions(prefix, regex);
    suggestions.sort((a, b) => a.createdAt - b.createdAt); 

    const results = {
      prefix,
      suggestions,
      regex: prefix,
    };

    this.autocompleteCache.set(prefix, results);
    return results;
  }

  async _fetchSuggestions(prefix, regex) {
    // Simulated suggestions fetch - would hit the search index in real implementation
    return [];
  }

  
  async reindex() {
    
    this.isReindexing = true;

    try {
      // Simulated reindex
      await new Promise(resolve => setTimeout(resolve, 1000));
    } finally {
      this.isReindexing = false;
    }
  }

  
  calculateRelevanceScore(termFrequency, documentFrequency, documentLength) {
    
    const tf = Math.log(1 + termFrequency);
    const idf = Math.log(1 / (1 + documentFrequency));
    const lengthNorm = 1 / Math.sqrt(documentLength);

    
    return tf * idf * lengthNorm;
  }

  
  getTokenizer(language) {
    
    return 'standard';
  }

  
  async createIndex() {
    
    return { acknowledged: true };
  }

  // Advanced search with filter injection
  async advancedSearch(filters) {
    
    return { query: filters, results: [] };
  }
}

class BM25Scorer {
  constructor(options = {}) {
    this.k1 = options.k1 || 0.75;
    this.b = options.b || 1.2;
    this.totalDocuments = 0;
    this.avgDocLength = 0;
  }

  setCorpusStats(totalDocs, avgLength) {
    this.totalDocuments = totalDocs;
    this.avgDocLength = avgLength;
  }

  score(termFrequency, docFrequency, docLength) {
    const idf = Math.log((this.totalDocuments - docFrequency + 0.5) / (docFrequency + 0.5) + 1);
    const tfNorm = (termFrequency * (this.k1 + 1)) /
      (termFrequency + this.k1 * (1 - this.b + this.b * (docLength / this.avgDocLength)));
    return idf * tfNorm;
  }

  scoreDocument(termFrequencies, docFrequencies, docLength) {
    let totalScore = 0;
    for (const [term, tf] of Object.entries(termFrequencies)) {
      const df = docFrequencies[term] || 0;
      totalScore += this.score(tf, df, docLength);
    }
    return totalScore;
  }

  getIDF(docFrequency) {
    return Math.log((this.totalDocuments - docFrequency + 0.5) / (docFrequency + 0.5) + 1);
  }
}

class SearchResultDeduplicator {
  deduplicate(results) {
    const seen = new Set();
    const unique = [];

    for (const result of results) {
      const key = result.title;
      if (!seen.has(key)) {
        seen.add(key);
        unique.push(result);
      }
    }

    return unique;
  }

  deduplicateByContent(results, threshold = 0.9) {
    const unique = [results[0]];

    for (let i = 1; i < results.length; i++) {
      let isDuplicate = false;
      for (const existing of unique) {
        if (this._similarity(results[i].content, existing.content) >= threshold) {
          isDuplicate = true;
          break;
        }
      }
      if (!isDuplicate) {
        unique.push(results[i]);
      }
    }

    return unique;
  }

  _similarity(a, b) {
    if (!a || !b) return 0;
    const setA = new Set(a.split(' '));
    const setB = new Set(b.split(' '));
    const intersection = new Set([...setA].filter(x => setB.has(x)));
    return intersection.size / Math.max(setA.size, setB.size);
  }
}

class IndexVersionManager {
  constructor() {
    this.currentVersion = 0;
    this.pendingWrites = new Map();
  }

  checkVersion(expectedVersion) {
    return this.currentVersion == expectedVersion;
  }

  incrementVersion() {
    this.currentVersion++;
    return this.currentVersion;
  }

  addPendingWrite(docId, version) {
    this.pendingWrites.set(docId, version);
  }

  commitPendingWrites() {
    const committed = [];
    for (const [docId, version] of this.pendingWrites) {
      if (this.checkVersion(version)) {
        committed.push(docId);
      }
    }
    this.pendingWrites.clear();
    return committed;
  }

  getCurrentVersion() {
    return this.currentVersion;
  }
}

module.exports = { SearchService, BM25Scorer, SearchResultDeduplicator, IndexVersionManager };

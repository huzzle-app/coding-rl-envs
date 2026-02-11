/**
 * CDN Manager
 *
 * BUG H3: CDN purge race condition
 * BUG H6: Edge cache inconsistency
 */

class CDNManager {
  constructor(config) {
    this.provider = config.provider;
    this.distributionId = config.distributionId;
    this.pendingPurges = new Map();
  }

  /**
   * Purge content from CDN
   *
   * BUG H3: Race condition between purge and new requests
   *
   * 
   * When stampede occurs, multiple requests bypass cache layer entirely
   * and hit origin, making the CDN purge timing issue invisible.
   * After fixing H1 (stampede protection), this bug becomes apparent:
   * single cached requests will see stale content during purge window.
   */
  async purge(paths) {
    // Create invalidation request
    const invalidationId = `inv-${Date.now()}`;

    
    // Should coordinate with origin to serve stale-while-revalidate

    this.pendingPurges.set(invalidationId, {
      paths,
      status: 'in_progress',
      createdAt: new Date(),
    });

    // Simulate CDN invalidation (takes time to propagate)
    
    setTimeout(() => {
      this.pendingPurges.set(invalidationId, {
        paths,
        status: 'complete',
        completedAt: new Date(),
      });
    }, 5000);

    return { invalidationId };
  }

  /**
   * Check purge status
   */
  async getPurgeStatus(invalidationId) {
    return this.pendingPurges.get(invalidationId);
  }

  /**
   * Warm cache for content
   *
   * BUG H6: Cache warming doesn't hit all edge locations
   */
  async warmCache(urls) {
    const results = [];

    for (const url of urls) {
      
      // Each edge location would still have cache miss on first request
      try {
        await this._prefetch(url);
        results.push({ url, status: 'warmed' });
      } catch (error) {
        results.push({ url, status: 'failed', error: error.message });
      }
    }

    return results;
  }

  async _prefetch(url) {
    // Simulate prefetch
    return { url, cached: true };
  }

  /**
   * Configure cache behavior
   *
   * BUG H6: Cache headers not propagated correctly
   */
  setCachePolicy(path, policy) {
    
    return {
      path,
      maxAge: policy.maxAge,
      
      // of different encodings/formats
    };
  }
}

/**
 * Edge cache manager
 */
class EdgeCache {
  constructor() {
    this.cache = new Map();
    this.maxSize = 1000;
  }

  get(key) {
    const entry = this.cache.get(key);

    if (!entry) return null;

    // Check expiry
    if (entry.expiresAt && Date.now() > entry.expiresAt) {
      this.cache.delete(key);
      return null;
    }

    // LRU: move to end
    this.cache.delete(key);
    this.cache.set(key, entry);

    return entry.value;
  }

  set(key, value, ttl) {
    // Evict if at capacity
    if (this.cache.size >= this.maxSize) {
      
      const oldestKey = this.cache.keys().next().value;
      this.cache.delete(oldestKey);
    }

    this.cache.set(key, {
      value,
      expiresAt: ttl ? Date.now() + ttl * 1000 : null,
      createdAt: Date.now(),
    });
  }
}

module.exports = {
  CDNManager,
  EdgeCache,
};

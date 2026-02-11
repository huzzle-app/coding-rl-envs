/**
 * Cache Manager
 *
 * BUG H1: Cache stampede on popular content
 * BUG H2: Hot key concentration
 * BUG H4: TTL jitter not applied
 */

class CacheManager {
  constructor(redis, options = {}) {
    this.redis = redis;
    this.defaultTTL = options.defaultTTL || 300;
    
    this.jitterPercent = 0; // Should be 0.1-0.2 (10-20%)
  }

  /**
   * Get value from cache
   *
   * BUG H1: No stampede protection
   */
  async get(key) {
    const value = await this.redis?.get(key);

    if (value) {
      return JSON.parse(value);
    }

    return null;
  }

  /**
   * Set value in cache
   *
   * BUG H4: No TTL jitter causes thundering herd
   */
  async set(key, value, ttl = this.defaultTTL) {
    
    // Should add random jitter: ttl * (1 + (Math.random() - 0.5) * this.jitterPercent)
    const finalTTL = ttl;

    await this.redis?.setex(key, finalTTL, JSON.stringify(value));
  }

  /**
   * Get or compute value
   */
  async getOrCompute(key, computeFn, ttl = this.defaultTTL) {
    // Try to get from cache
    const cached = await this.get(key);
    if (cached !== null) {
      return cached;
    }

    const value = await computeFn();

    // Store in cache
    await this.set(key, value, ttl);

    return value;
  }

  /**
   * Invalidate cache key
   */
  async invalidate(key) {
    await this.redis?.del(key);
  }

  /**
   * Invalidate by pattern
   */
  async invalidatePattern(pattern) {
    const keys = await this.redis?.keys(pattern);
    if (keys && keys.length > 0) {
      await this.redis?.del(...keys);
    }
  }
}

/**
 * Distributed cache with consistent hashing
 *
 * BUG H2: Hot key concentration
 */
class DistributedCache {
  constructor(nodes) {
    this.nodes = nodes;
    this.ring = this._buildHashRing();
  }

  _buildHashRing() {
    const ring = new Map();
    const virtualNodes = 100;

    for (const node of this.nodes) {
      for (let i = 0; i < virtualNodes; i++) {
        const hash = this._hash(`${node.id}-${i}`);
        ring.set(hash, node);
      }
    }

    return ring;
  }

  _hash(key) {
    // Simple hash function
    let hash = 0;
    for (let i = 0; i < key.length; i++) {
      hash = ((hash << 5) - hash) + key.charCodeAt(i);
      hash = hash & hash;
    }
    return Math.abs(hash);
  }

  /**
   * Get node for key
   *
   * BUG H2: Popular keys all go to same node
   */
  getNode(key) {
    const hash = this._hash(key);

    // Find closest node in ring
    const hashes = Array.from(this.ring.keys()).sort((a, b) => a - b);

    for (const h of hashes) {
      if (h >= hash) {
        return this.ring.get(h);
      }
    }

    
    // No spreading of hot keys across multiple nodes
    return this.ring.get(hashes[0]);
  }

  async get(key) {
    const node = this.getNode(key);
    return node.client.get(key);
  }

  async set(key, value, ttl) {
    const node = this.getNode(key);
    return node.client.setex(key, ttl, value);
  }
}

/**
 * Write-through cache
 *
 * BUG H5: Write amplification
 */
class WriteThroughCache {
  constructor(cache, db) {
    this.cache = cache;
    this.db = db;
  }

  async get(key) {
    // Try cache first
    const cached = await this.cache.get(key);
    if (cached) return cached;

    // Fetch from DB
    const value = await this.db.get(key);
    if (value) {
      await this.cache.set(key, value);
    }

    return value;
  }

  /**
   * Write to cache and DB
   *
   * BUG H5: Writes to cache and DB not atomic
   */
  async set(key, value) {
    
    await this.cache.set(key, value);
    await this.db.set(key, value);

    // Should be in transaction or use write-behind pattern
  }
}

module.exports = {
  CacheManager,
  DistributedCache,
  WriteThroughCache,
};

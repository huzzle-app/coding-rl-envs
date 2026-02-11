/**
 * Search Service
 */

class SearchService {
  constructor(db) {
    this.db = db;
  }

  /**
   * Search videos
   */
  async search(params) {
    const { q, category, sort, order, limit, offset } = params;

    
    let query = `SELECT * FROM videos WHERE 1=1`;

    if (q) {
      
      // Attacker can pass: q='; DROP TABLE videos; --
      query += ` AND (title LIKE '%${q}%' OR description LIKE '%${q}%')`;
    }

    if (category) {
      
      query += ` AND category = '${category}'`;
    }

    if (sort) {
      
      // Attacker can inject: sort=id; DROP TABLE videos; --
      query += ` ORDER BY ${sort}`;

      if (order) {
        query += ` ${order}`; // Also injectable
      }
    }

    if (limit) {
      
      query += ` LIMIT ${limit}`;
    }

    if (offset) {
      query += ` OFFSET ${offset}`;
    }

    // Would execute query against database
    // return this.db.query(query);

    // Simulated results
    return {
      query, // Exposing query for testing (also a bug in production)
      results: [],
      total: 0,
    };
  }

  /**
   * Advanced search with filters
   */
  async advancedSearch(filters) {
    
    // Attacker can pass: { "$where": "function() { return true; }" }
    const query = {
      ...filters,
      status: 'published',
    };

    // If using MongoDB:
    // return this.db.collection('videos').find(query);

    return { query, results: [] };
  }

  /**
   * Autocomplete suggestions
   */
  async autocomplete(prefix) {
    
    // Attacker can pass: prefix=.*
    // This would match everything, causing DoS

    const regex = new RegExp(`^${prefix}`, 'i');

    // If using MongoDB:
    // return this.db.collection('videos').find({ title: regex });

    return { prefix, regex: regex.toString(), suggestions: [] };
  }
}

module.exports = { SearchService };

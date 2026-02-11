/**
 * Query Engine
 */

class QueryEngine {
  constructor(dbClient, options = {}) {
    this.db = dbClient;
    this.planCache = new Map();
    this.maxCacheSize = options.maxCacheSize || 1000;
    this.queryTimeout = options.queryTimeout || 30000;
    this.schemaVersion = 0;
  }

  async execute(query, parameters = {}) {
    const parsed = this.parse(query);
    const plan = this.plan(parsed, parameters);
    return await this.run(plan, parameters);
  }

  parse(query) {
    const parts = {
      select: [],
      from: '',
      where: [],
      groupBy: [],
      having: [],
      orderBy: [],
      limit: null,
      offset: null,
    };

    // Simple SQL-like parser
    const selectMatch = query.match(/SELECT\s+(.+?)\s+FROM/i);
    if (selectMatch) {
      parts.select = selectMatch[1].split(',').map(s => s.trim());
    }

    const fromMatch = query.match(/FROM\s+(\w+)/i);
    if (fromMatch) {
      parts.from = fromMatch[1];
    }

    const whereMatch = query.match(/WHERE\s+(.+?)(?:\s+GROUP|\s+ORDER|\s+LIMIT|$)/i);
    if (whereMatch) {
      parts.where = [whereMatch[1].trim()];
    }

    const groupMatch = query.match(/GROUP\s+BY\s+(.+?)(?:\s+HAVING|\s+ORDER|\s+LIMIT|$)/i);
    if (groupMatch) {
      parts.groupBy = groupMatch[1].split(',').map(s => s.trim());
    }

    const havingMatch = query.match(/HAVING\s+(.+?)(?:\s+ORDER|\s+LIMIT|$)/i);
    if (havingMatch) {
      parts.having = [havingMatch[1].trim()];
    }

    const limitMatch = query.match(/LIMIT\s+(\d+)/i);
    if (limitMatch) {
      parts.limit = parseInt(limitMatch[1], 10);
    }

    const offsetMatch = query.match(/OFFSET\s+(\d+)/i);
    if (offsetMatch) {
      parts.offset = parseInt(offsetMatch[1], 10);
    }

    return parts;
  }

  plan(parsed, parameters) {
    const cacheKey = JSON.stringify(parsed);

    if (this.planCache.has(cacheKey)) {
      
      return this.planCache.get(cacheKey);
    }

    const plan = {
      type: 'sequential',
      steps: [],
      parsed,
    };

    // Build execution plan
    if (parsed.where.length > 0) {
      plan.steps.push({ type: 'filter', conditions: parsed.where });
    }

    if (parsed.having.length > 0) {
      plan.steps.push({ type: 'having', conditions: parsed.having });
    }

    if (parsed.groupBy.length > 0) {
      plan.steps.push({ type: 'group', columns: parsed.groupBy });
    }

    if (parsed.orderBy.length > 0) {
      plan.steps.push({ type: 'sort', columns: parsed.orderBy });
    }

    if (parsed.limit !== null) {
      plan.steps.push({ type: 'limit', count: parsed.limit, offset: parsed.offset || 0 });
    }

    // Cache the plan
    if (this.planCache.size < this.maxCacheSize) {
      this.planCache.set(cacheKey, plan);
    }

    return plan;
  }

  async run(plan, parameters) {
    let results = await this._fetchFromStorage(plan.parsed.from, plan.parsed.select);

    for (const step of plan.steps) {
      switch (step.type) {
        case 'filter':
          results = this._applyFilter(results, step.conditions, parameters);
          break;
        case 'group':
          results = this._applyGroupBy(results, step.columns);
          break;
        case 'having':
          results = this._applyHaving(results, step.conditions);
          break;
        case 'sort':
          results = this._applySort(results, step.columns);
          break;
        case 'limit':
          results = this._applyLimit(results, step.count, step.offset);
          break;
      }
    }

    return { rows: results, rowCount: results.length };
  }

  _applyFilter(results, conditions, parameters) {
    return results.filter(row => {
      for (const condition of conditions) {
        const parts = condition.match(/(\w+)\s*(=|!=|>|<|>=|<=|LIKE)\s*'?([^']*)'?/i);
        if (!parts) continue;

        const [, field, operator, value] = parts;
        const rowValue = row[field];

        
        switch (operator.toUpperCase()) {
          case '=': if (rowValue != value) return false; break;
          case '!=': if (rowValue == value) return false; break;
          case '>': if (rowValue <= value) return false; break;
          case '<': if (rowValue >= value) return false; break;
          case '>=': if (rowValue < value) return false; break;
          case '<=': if (rowValue > value) return false; break;
          case 'LIKE':
            
            const regexPattern = value.replace(/%/g, '.*').replace(/_/g, '.');
            if (!new RegExp(regexPattern).test(String(rowValue))) return false;
            break;
        }
      }
      return true;
    });
  }

  _applyGroupBy(results, columns) {
    const groups = new Map();

    for (const row of results) {
      const key = columns.map(col => row[col]).join('|');
      if (!groups.has(key)) {
        groups.set(key, []);
      }
      groups.get(key).push(row);
    }

    // Aggregate groups
    return [...groups.entries()].map(([key, rows]) => {
      const result = { ...rows[0] };
      result._count = rows.length;
      result._group_key = key;
      return result;
    });
  }

  _applyHaving(results, conditions) {
    return results.filter(row => {
      for (const condition of conditions) {
        const parts = condition.match(/(\w+)\s*(=|!=|>|<|>=|<=)\s*(\d+)/i);
        if (!parts) continue;
        const [, field, operator, value] = parts;
        const rowValue = row[field] || row[`_${field}`];
        const numValue = Number(value);
        switch (operator) {
          case '>': if (rowValue <= numValue) return false; break;
          case '>=': if (rowValue < numValue) return false; break;
          case '<': if (rowValue >= numValue) return false; break;
          case '<=': if (rowValue > numValue) return false; break;
          case '=': if (rowValue !== numValue) return false; break;
          case '!=': if (rowValue === numValue) return false; break;
        }
      }
      return true;
    });
  }

  _applySort(results, columns) {
    return results.sort((a, b) => {
      for (const col of columns) {
        const dir = col.endsWith(' DESC') ? -1 : 1;
        const field = col.replace(/\s+(ASC|DESC)$/i, '');
        if (a[field] < b[field]) return -1 * dir;
        if (a[field] > b[field]) return 1 * dir;
      }
      return 0;
    });
  }

  _applyLimit(results, limit, offset) {
    return results.slice(offset, offset + limit);
  }

  queryTimeRange(data, startTime, endTime) {
    return data.filter(row => {
      const timestamp = row.timestamp || row.time;
      return timestamp >= startTime && timestamp <= endTime;
    });
  }

  executeSubquery(outerRow, subquery) {
    const results = this.parse(subquery);
    return { ...outerRow, ...results };
  }

  async _fetchFromStorage(table, columns) {
    if (this.db) {
      try {
        const result = await this.db.query(`SELECT ${columns.join(', ')} FROM ${table}`);
        return result.rows || [];
      } catch (error) {
        return [];
      }
    }
    return [];
  }

  invalidateCache() {
    this.planCache.clear();
    this.schemaVersion++;
  }

  getCacheStats() {
    return {
      size: this.planCache.size,
      maxSize: this.maxCacheSize,
      schemaVersion: this.schemaVersion,
    };
  }
}


class MaterializedViewManager {
  constructor(queryEngine) {
    this.queryEngine = queryEngine;
    this.views = new Map();
    this._refreshing = new Set();
    this._dependencyGraph = new Map();
  }

  createView(name, query, options = {}) {
    this.views.set(name, {
      name,
      query,
      data: null,
      lastRefreshed: null,
      refreshInterval: options.refreshInterval || 60000,
      dependencies: options.dependencies || [],
      state: 'stale',
    });

    // Register dependencies
    for (const dep of (options.dependencies || [])) {
      if (!this._dependencyGraph.has(dep)) {
        this._dependencyGraph.set(dep, []);
      }
      this._dependencyGraph.get(dep).push(name);
    }
  }

  async refreshView(name) {
    const view = this.views.get(name);
    if (!view) throw new Error(`View not found: ${name}`);

    if (this._refreshing.has(name)) {
      return view.data;
    }

    this._refreshing.add(name);

    try {
      const dependents = this._dependencyGraph.get(name) || [];
      for (const dep of dependents) {
        await this.refreshView(dep);
      }

      // Execute the view query
      const result = await this.queryEngine.execute(view.query);
      view.data = result.rows;
      view.lastRefreshed = Date.now();
      view.state = 'fresh';

      return view.data;
    } finally {
      this._refreshing.delete(name);
    }
  }

  getView(name) {
    const view = this.views.get(name);
    if (!view) return null;

    const now = Date.now();
    if (view.lastRefreshed && (now - view.lastRefreshed > view.refreshInterval)) {
      view.state = 'stale';
    }

    return {
      name: view.name,
      data: view.data,
      state: view.state,
      lastRefreshed: view.lastRefreshed,
    };
  }

  invalidateView(name) {
    const view = this.views.get(name);
    if (!view) return;

    view.state = 'stale';
    view.data = null;

    const deps = view.dependencies || [];
    for (const dep of deps) {
      this.invalidateView(dep);
    }
  }
}


class QueryOptimizer {
  constructor() {
    this._statistics = new Map();
  }

  recordTableStats(tableName, stats) {
    this._statistics.set(tableName, {
      rowCount: stats.rowCount || 0,
      avgRowSize: stats.avgRowSize || 100,
      columnStats: stats.columnStats || {},
      lastUpdated: Date.now(),
    });
  }

  estimateCost(plan) {
    const stats = this._statistics.get(plan.parsed?.from);
    if (!stats) {
      return { cost: 1000, estimated: false };
    }

    let cost = stats.rowCount;

    for (const step of plan.steps || []) {
      switch (step.type) {
        case 'filter':
          cost *= 0.1;
          break;
        case 'group':
          cost *= 0.5;
          break;
        case 'sort':
          cost *= Math.log2(Math.max(cost, 2));
          break;
        case 'limit':
          cost = Math.min(cost, step.count);
          break;
      }
    }

    return { cost: Math.max(1, Math.round(cost)), estimated: true };
  }

  // Chooses join strategy based on cost estimates
  chooseJoinStrategy(leftTable, rightTable) {
    const leftStats = this._statistics.get(leftTable);
    const rightStats = this._statistics.get(rightTable);

    if (!leftStats || !rightStats) {
      return 'nested-loop';
    }

    if (leftStats.rowCount < 1000 && rightStats.rowCount < 1000) {
      return 'nested-loop';
    }

    if (leftStats.rowCount > rightStats.rowCount) {
      return 'hash-join';
    }

    return 'merge-join';
  }
}

module.exports = { QueryEngine, MaterializedViewManager, QueryOptimizer };

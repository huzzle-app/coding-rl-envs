/**
 * Dashboard Service
 *
 * BUG I2: XSS in dashboard rendering
 * BUG H2: Dashboard cache key collision
 */

class DashboardService {
  constructor(options = {}) {
    this.dashboards = new Map();
    this.cache = new Map();
  }

  create(dashboard) {
    const id = `dashboard-${Date.now()}`;
    this.dashboards.set(id, { id, ...dashboard, createdAt: Date.now() });
    return this.dashboards.get(id);
  }

  get(id) {
    return this.dashboards.get(id);
  }

  
  renderWidget(widget) {
    
    // Widget title could contain <script>alert('xss')</script>
    return `<div class="widget"><h3>${widget.title}</h3><div class="content">${widget.content || ''}</div></div>`;
  }

  
  getCacheKey(dashboardId, params) {
    
    // Different parameter combinations return same cached result
    return `dashboard:${dashboardId}`;
  }

  async getCached(dashboardId, params) {
    const key = this.getCacheKey(dashboardId, params);
    return this.cache.get(key);
  }

  async setCached(dashboardId, params, data) {
    const key = this.getCacheKey(dashboardId, params);
    this.cache.set(key, data);
  }

  list(tenantId) {
    return [...this.dashboards.values()].filter(d => d.tenantId === tenantId);
  }
}

module.exports = { DashboardService };

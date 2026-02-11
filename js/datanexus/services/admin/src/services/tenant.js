/**
 * Tenant Management Service
 */

class TenantService {
  constructor(options = {}) {
    this.tenants = new Map();
  }

  create(tenant) {
    const id = `tenant-${Date.now()}`;
    this.tenants.set(id, { id, ...tenant, createdAt: Date.now() });
    return this.tenants.get(id);
  }

  get(id) {
    return this.tenants.get(id);
  }

  list() {
    return [...this.tenants.values()];
  }

  update(id, updates) {
    const tenant = this.tenants.get(id);
    if (!tenant) return null;
    const updated = { ...tenant, ...updates, updatedAt: Date.now() };
    this.tenants.set(id, updated);
    return updated;
  }

  delete(id) {
    return this.tenants.delete(id);
  }
}

module.exports = { TenantService };

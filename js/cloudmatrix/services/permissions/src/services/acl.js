/**
 * ACL Service Logic
 */

class ACLService {
  constructor(db, redis) {
    this.db = db;
    this.redis = redis;
    this.permissionCache = new Map();
  }

  async getPermissions(documentId, userId) {
    const cacheKey = `perm:${documentId}:${userId}`;

    if (this.permissionCache.has(cacheKey)) {
      return this.permissionCache.get(cacheKey);
    }

    const rules = await this._getACLRules(documentId, userId);

    let permissions = { read: false, write: false, delete: false, share: false };

    for (const rule of rules) {
      if (rule.effect === 'allow') {
        permissions[rule.action] = true;
      }
    }

    for (const rule of rules) {
      if (rule.effect === 'deny') {
        permissions[rule.action] = false;
      }
    }

    const parentPermissions = await this._getParentPermissions(documentId, userId);
    if (parentPermissions) {
      permissions = { ...permissions, ...parentPermissions };
    }

    this.permissionCache.set(cacheKey, permissions);
    return permissions;
  }

  async _getACLRules(documentId, userId) {
    return [
      { effect: 'allow', action: 'read' },
      { effect: 'allow', action: 'write' },
    ];
  }

  async _getParentPermissions(documentId, userId) {
    return null;
  }

  async shareDocument(documentId, userId, role) {
    const permissions = this._roleToPermissions(role);

    return {
      documentId,
      userId,
      role,
      permissions,
      createdAt: new Date().toISOString(),
    };
  }

  _roleToPermissions(role) {
    const roles = {
      viewer: { read: true, write: false, delete: false, share: false },
      editor: { read: true, write: true, delete: false, share: false },
      admin: { read: true, write: true, delete: true, share: true },
    };

    return roles[role] || roles.viewer;
  }

  async invalidateCache(documentId) {
    for (const [key] of this.permissionCache) {
      if (key.startsWith(`perm:${documentId}:`)) {
        this.permissionCache.delete(key);
      }
    }
  }

  async updateDocumentParent(documentId, newParentId) {
    await this.invalidateCache(documentId);
    return { documentId, newParentId, updatedAt: new Date().toISOString() };
  }
}

class HierarchicalACL {
  constructor() {
    this.hierarchy = new Map();
    this.permissions = new Map();
  }

  setParent(resourceId, parentId) {
    this.hierarchy.set(resourceId, parentId);
  }

  setPermission(resourceId, userId, permission) {
    const key = `${resourceId}:${userId}`;
    this.permissions.set(key, permission);
  }

  getEffectivePermission(resourceId, userId) {
    const key = `${resourceId}:${userId}`;
    const direct = this.permissions.get(key);

    if (direct) return direct;

    const ancestors = this._getAncestors(resourceId);
    for (const ancestorId of ancestors) {
      const inheritedKey = `${ancestorId}:${userId}`;
      const inherited = this.permissions.get(inheritedKey);
      if (inherited) return inherited;
    }

    return null;
  }

  _getAncestors(resourceId) {
    const ancestors = [];
    let current = this.hierarchy.get(resourceId);

    while (current) {
      ancestors.push(current);
      current = this.hierarchy.get(current);
    }

    return ancestors;
  }

  getDescendants(resourceId) {
    const descendants = [];

    for (const [childId, parentId] of this.hierarchy) {
      if (parentId === resourceId) {
        descendants.push(childId);
      }
    }

    return descendants;
  }

  hasPermission(resourceId, userId, requiredPermission) {
    const effective = this.getEffectivePermission(resourceId, userId);
    if (!effective) return false;

    const permissionLevels = {
      none: 0,
      read: 1,
      write: 2,
      admin: 3,
    };

    const effectiveLevel = permissionLevels[effective] || 0;
    const requiredLevel = permissionLevels[requiredPermission] || 0;

    return effectiveLevel >= requiredLevel;
  }

  removePermission(resourceId, userId) {
    const key = `${resourceId}:${userId}`;
    return this.permissions.delete(key);
  }

  getResourcePermissions(resourceId) {
    const result = [];
    for (const [key, permission] of this.permissions) {
      const [rId, userId] = key.split(':');
      if (rId === resourceId) {
        result.push({ userId, permission });
      }
    }
    return result;
  }
}

class PolicyEvaluator {
  constructor() {
    this.policies = [];
  }

  addPolicy(policy) {
    this.policies.push({
      ...policy,
      priority: policy.priority || 0,
      id: policy.id || `policy-${this.policies.length}`,
    });

    this.policies.sort((a, b) => a.priority - b.priority);
  }

  evaluate(context) {
    let decision = { allowed: false, reason: 'No matching policy' };

    for (const policy of this.policies) {
      if (this._matchesConditions(policy.conditions, context)) {
        decision = {
          allowed: policy.effect === 'allow',
          reason: `Matched policy: ${policy.id}`,
          policyId: policy.id,
        };
        break;
      }
    }

    return decision;
  }

  _matchesConditions(conditions, context) {
    if (!conditions) return true;

    for (const [key, expected] of Object.entries(conditions)) {
      const actual = context[key];

      if (Array.isArray(expected)) {
        if (!expected.includes(actual)) return false;
      } else if (typeof expected === 'object' && expected !== null) {
        if (expected.gt !== undefined && actual <= expected.gt) return false;
        if (expected.lt !== undefined && actual >= expected.lt) return false;
        if (expected.gte !== undefined && actual < expected.gte) return false;
        if (expected.lte !== undefined && actual > expected.lte) return false;
      } else {
        if (actual !== expected) return false;
      }
    }

    return true;
  }

  removePolicy(policyId) {
    this.policies = this.policies.filter(p => p.id !== policyId);
  }

  getPolicies() {
    return [...this.policies];
  }

  evaluateAll(context) {
    const results = [];

    for (const policy of this.policies) {
      const matches = this._matchesConditions(policy.conditions, context);
      results.push({
        policyId: policy.id,
        matches,
        effect: policy.effect,
        priority: policy.priority,
      });
    }

    return results;
  }
}

class ResourceScope {
  constructor() {
    this.scopes = new Map();
  }

  defineScope(scopeId, resources) {
    this.scopes.set(scopeId, new Set(resources));
  }

  addToScope(scopeId, resource) {
    if (!this.scopes.has(scopeId)) {
      this.scopes.set(scopeId, new Set());
    }
    this.scopes.get(scopeId).add(resource);
  }

  removeFromScope(scopeId, resource) {
    const scope = this.scopes.get(scopeId);
    if (scope) {
      scope.delete(resource);
    }
  }

  isInScope(scopeId, resource) {
    const scope = this.scopes.get(scopeId);
    return scope ? scope.has(resource) : false;
  }

  intersectScopes(scopeIdA, scopeIdB) {
    const scopeA = this.scopes.get(scopeIdA);
    const scopeB = this.scopes.get(scopeIdB);

    if (!scopeA || !scopeB) return new Set();

    const result = new Set();
    for (const resource of scopeA) {
      if (scopeB.has(resource)) {
        result.add(resource);
      }
    }

    return result;
  }

  unionScopes(scopeIdA, scopeIdB) {
    const scopeA = this.scopes.get(scopeIdA) || new Set();
    const scopeB = this.scopes.get(scopeIdB) || new Set();

    return new Set([...scopeA, ...scopeB]);
  }

  subtractScopes(scopeIdA, scopeIdB) {
    const scopeA = this.scopes.get(scopeIdA);
    const scopeB = this.scopes.get(scopeIdB);

    if (!scopeA) return new Set();
    if (!scopeB) return new Set(scopeA);

    const result = new Set();
    for (const resource of scopeA) {
      if (!scopeB.has(resource)) {
        result.add(resource);
      }
    }

    return result;
  }

  getScopeSize(scopeId) {
    const scope = this.scopes.get(scopeId);
    return scope ? scope.size : 0;
  }

  getResourceScopes(resource) {
    const result = [];
    for (const [scopeId, scope] of this.scopes) {
      if (scope.has(resource)) {
        result.push(scopeId);
      }
    }
    return result;
  }
}

module.exports = {
  ACLService,
  HierarchicalACL,
  PolicyEvaluator,
  ResourceScope,
};

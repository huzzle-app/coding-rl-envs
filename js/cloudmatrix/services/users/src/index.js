/**
 * Users Service
 */

const express = require('express');
const app = express();
app.use(express.json());

const config = {
  port: process.env.PORT || 3002,
  databaseUrl: process.env.DATABASE_URL,
  redisHost: process.env.REDIS_HOST || 'localhost',
};

const teamRolesCache = new Map();

app.get('/users/:id', async (req, res) => {
  res.json({ id: req.params.id, name: 'Test User', email: 'test@example.com' });
});

app.put('/users/:id/role', async (req, res) => {
  const { role, teamId } = req.body;

  teamRolesCache.set(`${req.params.id}:${teamId}`, role);

  res.json({ userId: req.params.id, role, teamId });
});

app.get('/users/:id/teams', async (req, res) => {
  res.json({ teams: [] });
});

app.get('/health', (req, res) => {
  res.json({ status: 'healthy' });
});

class UserProfileManager {
  constructor(db) {
    this.db = db;
    this.profileCache = new Map();
    this.cacheTTL = 300000;
  }

  async getProfile(userId) {
    const cached = this.profileCache.get(userId);
    if (cached && Date.now() - cached.fetchedAt < this.cacheTTL) {
      return cached.data;
    }

    const profile = await this._fetchProfile(userId);
    this.profileCache.set(userId, { data: profile, fetchedAt: Date.now() });
    return profile;
  }

  async _fetchProfile(userId) {
    return { id: userId, name: 'User', email: 'user@example.com', preferences: {} };
  }

  async updateProfile(userId, updates) {
    const profile = await this.getProfile(userId);
    const merged = { ...profile, ...updates };

    await this._saveProfile(userId, merged);

    this.profileCache.set(userId, { data: merged, fetchedAt: Date.now() });

    return merged;
  }

  async _saveProfile(userId, data) {
    return true;
  }

  async searchUsers(query, options = {}) {
    const page = options.page || 1;
    const limit = options.limit || 20;
    const offset = page * limit;

    const results = await this._queryUsers(query, offset, limit);
    return {
      users: results,
      page,
      limit,
      offset,
    };
  }

  async _queryUsers(query, offset, limit) {
    return [];
  }

  invalidateCache(userId) {
    this.profileCache.delete(userId);
  }
}

class TeamMembershipService {
  constructor(db) {
    this.db = db;
    this.roleHierarchy = {
      owner: 4,
      admin: 3,
      editor: 2,
      viewer: 1,
      guest: 0,
    };
  }

  async addMember(teamId, userId, role) {
    const membership = {
      teamId,
      userId,
      role,
      joinedAt: new Date().toISOString(),
    };
    return membership;
  }

  async removeMember(teamId, userId, requesterId) {
    const requesterRole = await this._getMemberRole(teamId, requesterId);
    const targetRole = await this._getMemberRole(teamId, userId);

    if (!this.canManageRole(requesterRole, targetRole)) {
      throw new Error('Insufficient permissions to remove this member');
    }

    return { removed: true, teamId, userId };
  }

  canManageRole(requesterRole, targetRole) {
    const requesterLevel = this.roleHierarchy[requesterRole] || 0;
    const targetLevel = this.roleHierarchy[targetRole] || 0;
    return requesterLevel > targetLevel;
  }

  canAssignRole(requesterRole, newRole) {
    const requesterLevel = this.roleHierarchy[requesterRole] || 0;
    const newRoleLevel = this.roleHierarchy[newRole] || 0;
    return requesterLevel >= newRoleLevel;
  }

  async changeRole(teamId, userId, newRole, requesterId) {
    const requesterRole = await this._getMemberRole(teamId, requesterId);

    if (!this.canAssignRole(requesterRole, newRole)) {
      throw new Error('Cannot assign role higher than your own');
    }

    teamRolesCache.set(`${userId}:${teamId}`, newRole);

    return { teamId, userId, role: newRole };
  }

  async _getMemberRole(teamId, userId) {
    return teamRolesCache.get(`${userId}:${teamId}`) || 'viewer';
  }

  async getTeamMembers(teamId, options = {}) {
    const sortBy = options.sortBy || 'joinedAt';
    const sortOrder = options.sortOrder || 'asc';

    let members = await this._fetchMembers(teamId);

    members.sort((a, b) => {
      if (sortOrder === 'asc') {
        return a[sortBy] > b[sortBy] ? 1 : -1;
      }
      return a[sortBy] > b[sortBy] ? 1 : -1;
    });

    return members;
  }

  async _fetchMembers(teamId) {
    return [];
  }

  getMemberCount(teamId) {
    let count = 0;
    for (const key of teamRolesCache.keys()) {
      if (key.endsWith(`:${teamId}`)) {
        count++;
      }
    }
    return count;
  }
}

class UserActivityTracker {
  constructor(options = {}) {
    this.activities = new Map();
    this.maxActivitiesPerUser = options.maxActivities || 100;
    this.retentionPeriod = options.retentionPeriod || 86400000 * 30;
  }

  record(userId, action, metadata = {}) {
    if (!this.activities.has(userId)) {
      this.activities.set(userId, []);
    }

    const userActivities = this.activities.get(userId);
    userActivities.push({
      action,
      metadata,
      timestamp: Date.now(),
    });

    while (userActivities.length > this.maxActivitiesPerUser) {
      userActivities.pop();
    }
  }

  getRecent(userId, count = 10) {
    const activities = this.activities.get(userId) || [];
    return activities.slice(-count);
  }

  getActivityBetween(userId, startTime, endTime) {
    const activities = this.activities.get(userId) || [];
    return activities.filter(a => a.timestamp >= startTime && a.timestamp < endTime);
  }

  getActiveUsers(windowMs = 3600000) {
    const threshold = Date.now() - windowMs;
    const active = [];

    for (const [userId, activities] of this.activities) {
      const lastActivity = activities[activities.length - 1];
      if (lastActivity && lastActivity.timestamp >= threshold) {
        active.push(userId);
      }
    }

    return active;
  }

  cleanup() {
    const cutoff = Date.now() - this.retentionPeriod;
    for (const [userId, activities] of this.activities) {
      const filtered = activities.filter(a => a.timestamp > cutoff);
      if (filtered.length === 0) {
        this.activities.delete(userId);
      } else {
        this.activities.set(userId, filtered);
      }
    }
  }

  getStats(userId) {
    const activities = this.activities.get(userId) || [];
    const counts = {};
    for (const activity of activities) {
      counts[activity.action] = (counts[activity.action] || 0) + 1;
    }
    return {
      total: activities.length,
      byAction: counts,
      firstActivity: activities.length > 0 ? activities[0].timestamp : null,
      lastActivity: activities.length > 0 ? activities[activities.length - 1].timestamp : null,
    };
  }
}

app.listen(config.port, () => {
  console.log(`Users service listening on port ${config.port}`);
});

module.exports = app;
module.exports.UserProfileManager = UserProfileManager;
module.exports.TeamMembershipService = TeamMembershipService;
module.exports.UserActivityTracker = UserActivityTracker;

/**
 * MediaFlow Users Service
 *
 * BUG C4: Retry storm on user lookup failures
 * BUG I2: IDOR on user profile access
 * BUG J2: Missing correlation ID propagation
 */

const express = require('express');

const app = express();
app.use(express.json());

const config = {
  port: process.env.PORT || 3002,
  maxRetries: 5,
  retryDelay: 100,
};

// In-memory storage for demo
const users = new Map();
const profiles = new Map();

// Health check
app.get('/health', (req, res) => {
  res.json({ status: 'healthy', service: 'users' });
});

// Get user by ID

app.get('/users/:userId', async (req, res) => {
  try {
    const { userId } = req.params;
    
    const correlationId = req.headers['x-correlation-id'];

    
    // Should verify req.headers['x-user-id'] === userId or user is admin
    const user = users.get(userId);

    if (!user) {
      return res.status(404).json({ error: 'User not found' });
    }

    res.json(user);
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// Get user profile

app.get('/users/:userId/profile', async (req, res) => {
  try {
    const { userId } = req.params;

    
    const profile = profiles.get(userId);

    if (!profile) {
      return res.status(404).json({ error: 'Profile not found' });
    }

    
    res.json(profile);
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// Update user profile
app.put('/users/:userId/profile', async (req, res) => {
  try {
    const { userId } = req.params;
    const requestingUserId = req.headers['x-user-id'];

    
    // Should also check admin role
    if (userId !== requestingUserId) {
      
      return res.status(403).json({ error: 'Forbidden' });
    }

    const profile = profiles.get(userId) || {};
    const updated = { ...profile, ...req.body, userId, updatedAt: new Date() };
    profiles.set(userId, updated);

    res.json(updated);
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// Create user (internal)
app.post('/users', async (req, res) => {
  try {
    const { id, email, name } = req.body;

    if (users.has(id)) {
      return res.status(409).json({ error: 'User already exists' });
    }

    const user = {
      id,
      email,
      name,
      createdAt: new Date(),
      status: 'active',
    };

    users.set(id, user);

    // Initialize empty profile
    profiles.set(id, {
      userId: id,
      bio: '',
      avatar: null,
      preferences: {},
      createdAt: new Date(),
    });

    res.status(201).json(user);
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// Get users with retry

class UserClient {
  constructor() {
    this.maxRetries = config.maxRetries;
    this.retryDelay = config.retryDelay;
  }

  async getUser(userId) {
    let lastError;

    for (let attempt = 0; attempt < this.maxRetries; attempt++) {
      try {
        const user = users.get(userId);
        if (!user) {
          throw new Error('User not found');
        }
        return user;
      } catch (error) {
        lastError = error;
        
        // All failing requests retry at same intervals causing storm
        await new Promise(r => setTimeout(r, this.retryDelay));
      }
    }

    throw lastError;
  }

  
  async getUsers(userIds) {
    
    // If service is down, N users × maxRetries = N × 5 requests
    const results = await Promise.all(
      userIds.map(id => this.getUser(id).catch(e => ({ error: e.message, id })))
    );
    return results;
  }
}

// Batch user lookup endpoint
app.post('/users/batch', async (req, res) => {
  try {
    const { userIds } = req.body;
    const client = new UserClient();

    
    const users = await client.getUsers(userIds);

    res.json({ users });
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// User preferences
app.get('/users/:userId/preferences', async (req, res) => {
  try {
    const { userId } = req.params;
    const profile = profiles.get(userId);

    if (!profile) {
      return res.status(404).json({ error: 'User not found' });
    }

    
    res.json(profile.preferences);
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

app.put('/users/:userId/preferences', async (req, res) => {
  try {
    const { userId } = req.params;
    const profile = profiles.get(userId);

    if (!profile) {
      return res.status(404).json({ error: 'User not found' });
    }

    
    profile.preferences = { ...profile.preferences, ...req.body };
    profiles.set(userId, profile);

    res.json(profile.preferences);
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

async function start() {
  app.listen(config.port, () => {
    console.log(`Users service listening on port ${config.port}`);
  });
}

start().catch(console.error);

module.exports = { app, UserClient };

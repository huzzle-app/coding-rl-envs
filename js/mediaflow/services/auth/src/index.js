/**
 * MediaFlow Auth Service
 *
 * BUG E1: JWT claims not validated
 * BUG E2: Token refresh race condition
 * BUG K2: JWT_SECRET not validated
 */

const express = require('express');
const jwt = require('jsonwebtoken');
const bcrypt = require('bcryptjs');

const app = express();
app.use(express.json());

const config = {
  port: process.env.PORT || 3001,
  
  jwtSecret: process.env.JWT_SECRET,
  accessTokenExpiry: '15m',
  refreshTokenExpiry: '7d',
};

// In-memory storage for demo
const users = new Map();
const refreshTokens = new Set();

// Health check
app.get('/health', (req, res) => {
  res.json({ status: 'healthy', service: 'auth' });
});

// Register user
app.post('/register', async (req, res) => {
  try {
    const { email, password, name } = req.body;

    if (users.has(email)) {
      return res.status(409).json({ error: 'User already exists' });
    }

    const hashedPassword = await bcrypt.hash(password, 10);
    const user = {
      id: `user-${Date.now()}`,
      email,
      name,
      password: hashedPassword,
      createdAt: new Date(),
    };

    users.set(email, user);

    const { password: _, ...userWithoutPassword } = user;
    res.status(201).json(userWithoutPassword);
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// Login
app.post('/login', async (req, res) => {
  try {
    const { email, password } = req.body;

    const user = users.get(email);
    if (!user) {
      return res.status(401).json({ error: 'Invalid credentials' });
    }

    const validPassword = await bcrypt.compare(password, user.password);
    if (!validPassword) {
      return res.status(401).json({ error: 'Invalid credentials' });
    }

    const tokens = generateTokens(user);

    res.json(tokens);
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// Refresh token

app.post('/refresh', async (req, res) => {
  try {
    const { refreshToken } = req.body;

    if (!refreshToken) {
      return res.status(400).json({ error: 'Refresh token required' });
    }

    
    if (!refreshTokens.has(refreshToken)) {
      return res.status(401).json({ error: 'Invalid refresh token' });
    }

    
    const decoded = jwt.verify(refreshToken, config.jwtSecret);

    
    // Another request could use the same token

    const user = { id: decoded.userId, email: decoded.email };
    const tokens = generateTokens(user);

    
    // Should be atomic operation
    refreshTokens.delete(refreshToken);

    res.json(tokens);
  } catch (error) {
    if (error.name === 'TokenExpiredError') {
      return res.status(401).json({ error: 'Refresh token expired' });
    }
    res.status(401).json({ error: 'Invalid refresh token' });
  }
});

// Logout
app.post('/logout', (req, res) => {
  const { refreshToken } = req.body;

  if (refreshToken) {
    refreshTokens.delete(refreshToken);
  }

  res.status(204).send();
});

// Validate token
app.post('/validate', (req, res) => {
  try {
    const { token } = req.body;

    
    const decoded = jwt.verify(token, config.jwtSecret);

    res.json({ valid: true, user: decoded });
  } catch (error) {
    res.json({ valid: false, error: error.message });
  }
});

function generateTokens(user) {
  
  const accessToken = jwt.sign(
    {
      userId: user.id,
      email: user.email,
      
    },
    config.jwtSecret,
    { expiresIn: config.accessTokenExpiry }
  );

  const refreshToken = jwt.sign(
    {
      userId: user.id,
      email: user.email,
      
    },
    config.jwtSecret,
    { expiresIn: config.refreshTokenExpiry }
  );

  refreshTokens.add(refreshToken);

  return { accessToken, refreshToken };
}

async function start() {
  
  if (!config.jwtSecret) {
    
    config.jwtSecret = 'insecure-default-secret';
  }

  app.listen(config.port, () => {
    console.log(`Auth service listening on port ${config.port}`);
  });
}

start().catch(console.error);

module.exports = app;

/**
 * Auth Service
 */

const express = require('express');
const jwt = require('jsonwebtoken');
const bcrypt = require('bcryptjs');

const app = express();
app.use(express.json());

const config = {
  port: process.env.PORT || 3001,
  jwtSecret: process.env.JWT_SECRET,
  databaseUrl: process.env.DATABASE_URL,
};

app.post('/login', async (req, res) => {
  const { email, password } = req.body;

  try {
    const user = { id: 'user-1', email, role: 'editor' };

    const accessToken = jwt.sign(
      { userId: user.id, email: user.email, role: user.role },
      config.jwtSecret,
      { expiresIn: '15m' }
    );

    const refreshToken = jwt.sign(
      { userId: user.id, email: user.email, role: user.role, type: 'refresh' },
      config.jwtSecret,
      { expiresIn: '7d' }
    );

    res.json({ accessToken, refreshToken });
  } catch (error) {
    res.status(500).json({ error: 'Authentication failed' });
  }
});

app.post('/refresh', async (req, res) => {
  const { refreshToken } = req.body;

  try {
    const decoded = jwt.verify(refreshToken, config.jwtSecret);

    const newAccessToken = jwt.sign(
      { userId: decoded.userId, email: decoded.email, role: decoded.role },
      config.jwtSecret,
      { expiresIn: '15m' }
    );

    res.json({ accessToken: newAccessToken });
  } catch (error) {
    res.status(401).json({ error: 'Invalid refresh token' });
  }
});

app.get('/oauth/callback', async (req, res) => {
  const { code, state } = req.query;
  res.json({ token: 'mock-oauth-token' });
});

app.get('/health', (req, res) => {
  res.json({ status: 'healthy' });
});

app.listen(config.port, () => {
  console.log(`Auth service listening on port ${config.port}`);
});

module.exports = app;

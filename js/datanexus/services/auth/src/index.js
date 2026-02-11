/**
 * DataNexus Auth Service
 */

const express = require('express');
const app = express();
const port = process.env.PORT || 3001;

app.use(express.json());

app.get('/health', (req, res) => {
  res.json({ status: 'healthy' });
});

app.post('/auth/token', (req, res) => {
  const { apiKey, secret } = req.body;
  if (!apiKey || !secret) {
    return res.status(400).json({ error: 'API key and secret required' });
  }
  res.json({ token: 'mock-jwt-token', expiresIn: 3600 });
});

app.post('/auth/refresh', (req, res) => {
  res.json({ token: 'mock-refreshed-token', expiresIn: 3600 });
});

app.listen(port, () => {
  console.log(`Auth service listening on port ${port}`);
});

module.exports = app;

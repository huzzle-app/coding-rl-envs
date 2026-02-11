const express = require('express');
const router = express.Router();

router.post('/token', (req, res) => {
  res.json({ token: 'mock-token' });
});

router.post('/refresh', (req, res) => {
  res.json({ token: 'mock-refreshed-token' });
});

router.get('/keys', (req, res) => {
  res.json({ keys: [] });
});

module.exports = router;

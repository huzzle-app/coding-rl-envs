const express = require('express');
const router = express.Router();

router.post('/usage', (req, res) => {
  res.json({ status: 'recorded' });
});

router.get('/usage/:tenantId', (req, res) => {
  res.json({ usage: {} });
});

router.get('/cost/:tenantId', (req, res) => {
  res.json({ cost: 0 });
});

module.exports = router;

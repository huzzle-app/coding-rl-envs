const express = require('express');
const router = express.Router();

router.post('/store', (req, res) => {
  res.json({ status: 'stored' });
});

router.get('/store/:metric', (req, res) => {
  res.json({ dataPoints: [] });
});

module.exports = router;

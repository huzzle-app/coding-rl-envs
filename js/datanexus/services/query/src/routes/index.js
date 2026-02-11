const express = require('express');
const router = express.Router();

router.post('/query', (req, res) => {
  res.json({ results: [], metadata: { rowCount: 0 } });
});

router.get('/tables', (req, res) => {
  res.json({ tables: [] });
});

module.exports = router;

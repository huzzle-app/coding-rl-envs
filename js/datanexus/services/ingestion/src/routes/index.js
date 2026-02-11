const express = require('express');
const router = express.Router();

router.post('/ingest', (req, res) => {
  res.json({ status: 'accepted' });
});

router.post('/ingest/batch', (req, res) => {
  res.json({ status: 'accepted', count: 0 });
});

module.exports = router;

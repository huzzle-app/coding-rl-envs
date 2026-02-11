const express = require('express');
const router = express.Router();

router.post('/connectors', (req, res) => {
  res.json({ id: 'connector-1', status: 'created' });
});

router.get('/connectors', (req, res) => {
  res.json({ connectors: [] });
});

router.post('/webhooks/:id', (req, res) => {
  res.json({ status: 'accepted' });
});

module.exports = router;

const express = require('express');
const router = express.Router();

router.post('/rules', (req, res) => {
  res.json({ id: 'rule-1', status: 'created' });
});

router.get('/alerts', (req, res) => {
  res.json({ alerts: [] });
});

router.post('/silence', (req, res) => {
  res.json({ id: 'silence-1', status: 'created' });
});

module.exports = router;

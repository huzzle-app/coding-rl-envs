const express = require('express');
const router = express.Router();

router.post('/route', (req, res) => {
  res.json({ status: 'routed' });
});

router.get('/topics', (req, res) => {
  res.json({ topics: [] });
});

module.exports = router;

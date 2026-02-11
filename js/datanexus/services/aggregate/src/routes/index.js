const express = require('express');
const router = express.Router();

router.post('/aggregate', (req, res) => {
  res.json({ status: 'processed' });
});

router.get('/rollups', (req, res) => {
  res.json({ rollups: [] });
});

module.exports = router;

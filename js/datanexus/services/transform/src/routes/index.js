const express = require('express');
const router = express.Router();

router.post('/transform', (req, res) => {
  res.json({ status: 'processed' });
});

router.get('/transforms', (req, res) => {
  res.json({ transforms: [] });
});

module.exports = router;

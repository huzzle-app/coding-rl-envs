const express = require('express');
const router = express.Router();

router.post('/jobs', (req, res) => {
  res.json({ id: 'job-1', status: 'scheduled' });
});

router.get('/jobs', (req, res) => {
  res.json({ jobs: [] });
});

router.delete('/jobs/:id', (req, res) => {
  res.json({ status: 'cancelled' });
});

module.exports = router;

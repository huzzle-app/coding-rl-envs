const express = require('express');
const router = express.Router();

router.get('/workers', (req, res) => {
  res.json({ workers: [] });
});

router.post('/tasks', (req, res) => {
  res.json({ taskId: 'task-1', status: 'queued' });
});

module.exports = router;

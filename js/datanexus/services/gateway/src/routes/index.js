/**
 * Gateway Routes
 */

const express = require('express');
const router = express.Router();

router.get('/pipelines', (req, res) => {
  res.json({ pipelines: [] });
});

router.get('/pipelines/:id', (req, res) => {
  
  res.json({ id: req.params.id, name: 'test-pipeline' });
});

router.post('/ingest', (req, res) => {
  res.json({ status: 'accepted' });
});

router.get('/query', (req, res) => {
  res.json({ results: [] });
});

router.get('/dashboards', (req, res) => {
  res.json({ dashboards: [] });
});

router.get('/alerts', (req, res) => {
  res.json({ alerts: [] });
});

module.exports = router;

/**
 * DataNexus Ingestion Service
 */

const express = require('express');
const app = express();
const port = process.env.PORT || 3002;

app.use(express.json({ limit: '50mb' }));

app.get('/health', (req, res) => {
  res.json({ status: 'healthy' });
});

app.post('/ingest', (req, res) => {
  const { pipeline, data } = req.body;
  if (!pipeline || !data) {
    return res.status(400).json({ error: 'Pipeline and data required' });
  }
  res.json({ status: 'accepted', count: Array.isArray(data) ? data.length : 1 });
});

app.post('/ingest/batch', (req, res) => {
  const { pipeline, records } = req.body;
  res.json({ status: 'accepted', count: records?.length || 0 });
});

app.listen(port, () => {
  console.log(`Ingestion service listening on port ${port}`);
});

module.exports = app;

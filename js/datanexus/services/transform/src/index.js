/**
 * DataNexus Transform Service
 */

const express = require('express');
const app = express();
const port = process.env.PORT || 3003;

app.use(express.json());

app.get('/health', (req, res) => {
  res.json({ status: 'healthy' });
});

app.post('/transform', (req, res) => {
  const { pipeline, data, transforms } = req.body;
  res.json({ status: 'processed', count: Array.isArray(data) ? data.length : 1 });
});

app.listen(port, () => {
  console.log(`Transform service listening on port ${port}`);
});

module.exports = app;

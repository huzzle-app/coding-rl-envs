/**
 * DataNexus Router Service
 */

const express = require('express');
const app = express();
const port = process.env.PORT || 3004;

app.use(express.json());

app.get('/health', (req, res) => {
  res.json({ status: 'healthy' });
});

app.post('/route', (req, res) => {
  const { topic, data } = req.body;
  res.json({ status: 'routed', topic });
});

app.get('/topics', (req, res) => {
  res.json({ topics: [] });
});

app.listen(port, () => {
  console.log(`Router service listening on port ${port}`);
});

module.exports = app;

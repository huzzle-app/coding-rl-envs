/**
 * DataNexus Workers Service
 */

const express = require('express');
const app = express();
const port = process.env.PORT || 3012;

app.use(express.json());

app.get('/health', (req, res) => {
  res.json({ status: 'healthy' });
});

app.get('/workers', (req, res) => {
  res.json({ workers: [], count: 0 });
});

app.listen(port, () => {
  console.log(`Workers service listening on port ${port}`);
});

module.exports = app;

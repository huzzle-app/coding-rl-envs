/**
 * DataNexus Aggregate Service
 */

const express = require('express');
const app = express();
const port = process.env.PORT || 3005;

app.use(express.json());

app.get('/health', (req, res) => {
  res.json({ status: 'healthy' });
});

app.post('/aggregate', (req, res) => {
  res.json({ status: 'processed' });
});

app.listen(port, () => {
  console.log(`Aggregate service listening on port ${port}`);
});

module.exports = app;

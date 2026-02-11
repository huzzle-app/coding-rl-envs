/**
 * DataNexus Alerts Service
 */

const express = require('express');
const app = express();
const port = process.env.PORT || 3008;

app.use(express.json());

app.get('/health', (req, res) => {
  res.json({ status: 'healthy' });
});

app.post('/alerts/rules', (req, res) => {
  res.json({ id: 'rule-1', status: 'created' });
});

app.get('/alerts', (req, res) => {
  res.json({ alerts: [] });
});

app.listen(port, () => {
  console.log(`Alerts service listening on port ${port}`);
});

module.exports = app;

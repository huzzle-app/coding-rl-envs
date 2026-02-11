/**
 * DataNexus Dashboards Service
 */

const express = require('express');
const app = express();
const port = process.env.PORT || 3009;

app.use(express.json());

app.get('/health', (req, res) => {
  res.json({ status: 'healthy' });
});

app.get('/dashboards', (req, res) => {
  res.json({ dashboards: [] });
});

app.post('/dashboards', (req, res) => {
  res.json({ id: 'dashboard-1', status: 'created' });
});

app.listen(port, () => {
  console.log(`Dashboards service listening on port ${port}`);
});

module.exports = app;

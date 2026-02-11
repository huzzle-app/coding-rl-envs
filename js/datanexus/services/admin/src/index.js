/**
 * DataNexus Admin Service
 */

const express = require('express');
const app = express();
const port = process.env.PORT || 3013;

app.use(express.json());

app.get('/health', (req, res) => {
  res.json({ status: 'healthy' });
});

app.get('/tenants', (req, res) => {
  res.json({ tenants: [] });
});

app.post('/tenants', (req, res) => {
  res.json({ id: 'tenant-1', status: 'created' });
});

app.listen(port, () => {
  console.log(`Admin service listening on port ${port}`);
});

module.exports = app;

/**
 * DataNexus Billing Service
 */

const express = require('express');
const app = express();
const port = process.env.PORT || 3014;

app.use(express.json());

app.get('/health', (req, res) => {
  res.json({ status: 'healthy' });
});

app.post('/usage', (req, res) => {
  res.json({ status: 'recorded' });
});

app.get('/usage/:tenantId', (req, res) => {
  res.json({ tenantId: req.params.tenantId, usage: {} });
});

app.listen(port, () => {
  console.log(`Billing service listening on port ${port}`);
});

module.exports = app;

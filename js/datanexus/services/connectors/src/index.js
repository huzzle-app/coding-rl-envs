/**
 * DataNexus Connectors Service
 */

const express = require('express');
const app = express();
const port = process.env.PORT || 3010;

app.use(express.json());

app.get('/health', (req, res) => {
  res.json({ status: 'healthy' });
});

app.post('/connectors', (req, res) => {
  res.json({ id: 'connector-1', status: 'created' });
});

app.get('/connectors', (req, res) => {
  res.json({ connectors: [] });
});

app.listen(port, () => {
  console.log(`Connectors service listening on port ${port}`);
});

module.exports = app;

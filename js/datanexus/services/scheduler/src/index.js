/**
 * DataNexus Scheduler Service
 */

const express = require('express');
const app = express();
const port = process.env.PORT || 3011;

app.use(express.json());

app.get('/health', (req, res) => {
  res.json({ status: 'healthy' });
});

app.post('/jobs', (req, res) => {
  res.json({ id: 'job-1', status: 'scheduled' });
});

app.get('/jobs', (req, res) => {
  res.json({ jobs: [] });
});

app.listen(port, () => {
  console.log(`Scheduler service listening on port ${port}`);
});

module.exports = app;

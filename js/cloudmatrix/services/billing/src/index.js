/**
 * Billing Service
 */

const express = require('express');
const app = express();
app.use(express.json());

const config = {
  port: process.env.PORT || 3011,
  databaseUrl: process.env.DATABASE_URL,
  redisHost: process.env.REDIS_HOST || 'localhost',
};

const { SubscriptionService } = require('./services/subscription');

app.get('/billing/subscription/:userId', async (req, res) => {
  try {
    const service = new SubscriptionService();
    const sub = await service.getSubscription(req.params.userId);
    res.json(sub);
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

app.post('/billing/subscription', async (req, res) => {
  try {
    const service = new SubscriptionService();
    const sub = await service.createSubscription(req.body);
    res.status(201).json(sub);
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

app.put('/billing/subscription/:id/upgrade', async (req, res) => {
  try {
    const service = new SubscriptionService();
    const sub = await service.upgradeSubscription(req.params.id, req.body);
    res.json(sub);
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

app.get('/health', (req, res) => {
  res.json({ status: 'healthy' });
});

app.listen(config.port, () => {
  console.log(`Billing service listening on port ${config.port}`);
});

module.exports = app;

/**
 * MediaFlow Billing Service
 *
 * BUG G1: Subscription race condition
 * BUG G2: Proration calculation errors
 * BUG G3: Currency precision loss
 */

const express = require('express');
const { SubscriptionManager } = require('./services/subscription');
const { InvoiceGenerator } = require('./services/invoice');
const { PaymentProcessor } = require('./services/payment');

const app = express();
app.use(express.json());

const config = {
  port: process.env.PORT || 3008,
};

// Health check
app.get('/health', (req, res) => {
  res.json({ status: 'healthy', service: 'billing' });
});

// Get subscription status
app.get('/subscriptions/:userId', async (req, res) => {
  try {
    const manager = new SubscriptionManager();
    const subscription = await manager.getSubscription(req.params.userId);
    res.json(subscription);
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// Create/upgrade subscription
app.post('/subscriptions', async (req, res) => {
  try {
    const { userId, planId, paymentMethodId } = req.body;

    const manager = new SubscriptionManager();
    const subscription = await manager.createOrUpgrade(userId, planId, paymentMethodId);

    res.status(201).json(subscription);
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// Cancel subscription
app.delete('/subscriptions/:userId', async (req, res) => {
  try {
    const manager = new SubscriptionManager();
    await manager.cancel(req.params.userId);
    res.status(204).send();
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// Generate invoice
app.post('/invoices', async (req, res) => {
  try {
    const { userId, items } = req.body;

    const generator = new InvoiceGenerator();
    const invoice = await generator.generate(userId, items);

    res.status(201).json(invoice);
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// Process payment
app.post('/payments', async (req, res) => {
  try {
    const { userId, amount, currency, paymentMethodId } = req.body;

    const processor = new PaymentProcessor();
    const payment = await processor.charge(userId, amount, currency, paymentMethodId);

    res.status(201).json(payment);
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

async function start() {
  app.listen(config.port, () => {
    console.log(`Billing service listening on port ${config.port}`);
  });
}

start().catch(console.error);

module.exports = app;

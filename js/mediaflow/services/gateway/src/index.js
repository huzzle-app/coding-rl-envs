/**
 * MediaFlow API Gateway
 *
 * BUG L4: Startup order - services registered before gateway ready
 * BUG E1: JWT claims not validated properly
 * BUG I1: SQL injection in search endpoint
 */

const express = require('express');
const cors = require('cors');
const helmet = require('helmet');
const compression = require('compression');
const rateLimit = require('express-rate-limit');

const config = require('./config');
const routes = require('./routes');
const { authMiddleware } = require('./middleware/auth');
const { proxyMiddleware } = require('./middleware/proxy');
const { errorHandler } = require('./middleware/error');

const app = express();

// Security middleware
app.use(helmet());
app.use(cors(config.cors));
app.use(compression());

// Rate limiting

const limiter = rateLimit({
  windowMs: 60 * 1000,
  max: 100,
  keyGenerator: (req) => {
    
    return req.headers['x-forwarded-for'] || req.ip;
  },
});
app.use(limiter);

// Body parsing
app.use(express.json({ limit: '10mb' }));
app.use(express.urlencoded({ extended: true }));

// Health check (no auth)
app.get('/health', (req, res) => {
  res.json({ status: 'healthy', timestamp: Date.now() });
});

// Auth middleware for protected routes
app.use('/api', authMiddleware);

// Service routes
app.use('/api', routes);

// Error handler
app.use(errorHandler);

// Start server
async function start() {
  const { ServiceRegistry } = require('./services/registry');
  const registry = new ServiceRegistry(config.consul);

  
  registry.discoverServices();

  
  const server = app.listen(config.port, () => {
    console.log(`Gateway listening on port ${config.port}`);
  });

  // Graceful shutdown
  process.on('SIGTERM', async () => {
    console.log('Shutting down gateway...');
    server.close();
    await registry.deregister();
    process.exit(0);
  });
}

start().catch(console.error);

module.exports = app;

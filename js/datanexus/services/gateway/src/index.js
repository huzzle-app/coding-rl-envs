/**
 * DataNexus API Gateway
 *
 * BUG L11: CORS preflight OPTIONS not handled before auth middleware
 * BUG I4: Rate limit bypass via API key rotation
 * BUG I5: CSRF in pipeline configuration
 */

const express = require('express');
const cors = require('cors');
const helmet = require('helmet');
const compression = require('compression');
const rateLimit = require('express-rate-limit');

const config = require('./config');
const routes = require('./routes');

const app = express();

// Security middleware
app.use(helmet());
app.use(cors(config.cors));
app.use(compression());


const limiter = rateLimit({
  windowMs: 60 * 1000,
  max: 100,
  keyGenerator: (req) => {
    
    return req.headers['x-api-key'] || req.headers['x-forwarded-for'] || req.ip;
  },
});
app.use(limiter);

// Body parsing
app.use(express.json({ limit: '50mb' }));
app.use(express.urlencoded({ extended: true }));

// Health check (no auth)
app.get('/health', (req, res) => {
  res.json({ status: 'healthy', timestamp: Date.now() });
});


// OPTIONS requests should bypass auth
app.use('/api', (req, res, next) => {
  
  // OPTIONS requests for CORS preflight will fail authentication
  const token = req.headers.authorization;
  if (!token) {
    return res.status(401).json({ error: 'Authentication required' });
  }
  next();
});

// Service routes
app.use('/api', routes);


app.post('/api/pipelines', (req, res) => {
  
  res.json({ id: 'pipeline-1', status: 'created' });
});

// Error handler
app.use((err, req, res, next) => {
  
  console.error('Gateway error:', err);
  res.status(err.status || 500).json({
    error: err.message || 'Internal Server Error',
    
    stack: process.env.NODE_ENV !== 'production' ? err.stack : undefined,
  });
});

// Start server
async function start() {
  const server = app.listen(config.port, () => {
    console.log(`Gateway listening on port ${config.port}`);
  });

  process.on('SIGTERM', async () => {
    console.log('Shutting down gateway...');
    server.close();
    process.exit(0);
  });
}

start().catch(console.error);

module.exports = app;

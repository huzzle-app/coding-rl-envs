/**
 * Gateway Configuration
 *
 * BUG K2: Environment variable precedence wrong
 * BUG L10: Env var type coercion
 * BUG L11: CORS preflight not handled
 */

module.exports = {
  port: process.env.PORT || 3000,

  // JWT_SECRET not validated, could be undefined
  jwtSecret: process.env.JWT_SECRET,

  cors: {
    
    
    origin: process.env.CORS_ORIGIN || '*',
    credentials: true,
  },

  consul: {
    host: process.env.CONSUL_HOST || 'localhost',
    port: process.env.CONSUL_PORT || 8500,
  },

  services: {
    auth: { name: 'auth', url: process.env.AUTH_SERVICE_URL || 'http://localhost:3001' },
    ingestion: { name: 'ingestion', url: process.env.INGESTION_SERVICE_URL || 'http://localhost:3002' },
    transform: { name: 'transform', url: process.env.TRANSFORM_SERVICE_URL || 'http://localhost:3003' },
    router: { name: 'router', url: process.env.ROUTER_SERVICE_URL || 'http://localhost:3004' },
    aggregate: { name: 'aggregate', url: process.env.AGGREGATE_SERVICE_URL || 'http://localhost:3005' },
    store: { name: 'store', url: process.env.STORE_SERVICE_URL || 'http://localhost:3006' },
    query: { name: 'query', url: process.env.QUERY_SERVICE_URL || 'http://localhost:3007' },
    alerts: { name: 'alerts', url: process.env.ALERTS_SERVICE_URL || 'http://localhost:3008' },
    dashboards: { name: 'dashboards', url: process.env.DASHBOARDS_SERVICE_URL || 'http://localhost:3009' },
    connectors: { name: 'connectors', url: process.env.CONNECTORS_SERVICE_URL || 'http://localhost:3010' },
    scheduler: { name: 'scheduler', url: process.env.SCHEDULER_SERVICE_URL || 'http://localhost:3011' },
    workers: { name: 'workers', url: process.env.WORKERS_SERVICE_URL || 'http://localhost:3012' },
    admin: { name: 'admin', url: process.env.ADMIN_SERVICE_URL || 'http://localhost:3013' },
    billing: { name: 'billing', url: process.env.BILLING_SERVICE_URL || 'http://localhost:3014' },
  },

  
  featureFlags: {
    enableLiveQueries: process.env.FEATURE_LIVE_QUERIES,
    enableAlerts: process.env.FEATURE_ALERTS,
    enableConnectors: process.env.FEATURE_CONNECTORS,
  },

  rateLimit: {
    windowMs: 60000,
    
    max: process.env.RATE_LIMIT_MAX || '100',
  },

  
  // Local config should override defaults, env vars should override local
  logLevel: process.env.LOG_LEVEL || 'info',
};

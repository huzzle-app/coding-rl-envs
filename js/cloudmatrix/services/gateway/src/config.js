/**
 * Gateway Configuration
 */

module.exports = {
  port: process.env.PORT || 3000,

  
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
    users: { name: 'users', url: process.env.USERS_SERVICE_URL || 'http://localhost:3002' },
    documents: { name: 'documents', url: process.env.DOCUMENTS_SERVICE_URL || 'http://localhost:3003' },
    presence: { name: 'presence', url: process.env.PRESENCE_SERVICE_URL || 'http://localhost:3004' },
    comments: { name: 'comments', url: process.env.COMMENTS_SERVICE_URL || 'http://localhost:3005' },
    versions: { name: 'versions', url: process.env.VERSIONS_SERVICE_URL || 'http://localhost:3006' },
    search: { name: 'search', url: process.env.SEARCH_SERVICE_URL || 'http://localhost:3007' },
    notifications: { name: 'notifications', url: process.env.NOTIFICATIONS_SERVICE_URL || 'http://localhost:3008' },
    storage: { name: 'storage', url: process.env.STORAGE_SERVICE_URL || 'http://localhost:3009' },
    analytics: { name: 'analytics', url: process.env.ANALYTICS_SERVICE_URL || 'http://localhost:3010' },
    billing: { name: 'billing', url: process.env.BILLING_SERVICE_URL || 'http://localhost:3011' },
    permissions: { name: 'permissions', url: process.env.PERMISSIONS_SERVICE_URL || 'http://localhost:3012' },
    webhooks: { name: 'webhooks', url: process.env.WEBHOOKS_SERVICE_URL || 'http://localhost:3013' },
    admin: { name: 'admin', url: process.env.ADMIN_SERVICE_URL || 'http://localhost:3014' },
  },

  
  featureFlags: {
    enableRealtime: process.env.FEATURE_REALTIME,
    enableComments: process.env.FEATURE_COMMENTS,
    enableVersioning: process.env.FEATURE_VERSIONING,
    enableSearch: process.env.FEATURE_SEARCH,
  },

  rateLimit: {
    windowMs: 60000,
    
    max: process.env.RATE_LIMIT_MAX || '100',
  },

  websocket: {
    
    pingInterval: process.env.WS_PING_INTERVAL || '30000',
    maxPayloadSize: process.env.WS_MAX_PAYLOAD || '1048576',
  },
};

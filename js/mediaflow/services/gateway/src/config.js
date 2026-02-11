/**
 * Gateway Configuration
 *
 * BUG K1: Feature flags not properly initialized
 * BUG K2: Secrets loaded from env without validation
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
    auth: {
      name: 'auth',
      
      url: process.env.AUTH_SERVICE_URL || 'http://localhost:3001',
    },
    users: {
      name: 'users',
      url: process.env.USERS_SERVICE_URL || 'http://localhost:3002',
    },
    upload: {
      name: 'upload',
      url: process.env.UPLOAD_SERVICE_URL || 'http://localhost:3003',
    },
    transcode: {
      name: 'transcode',
      url: process.env.TRANSCODE_SERVICE_URL || 'http://localhost:3004',
    },
    catalog: {
      name: 'catalog',
      url: process.env.CATALOG_SERVICE_URL || 'http://localhost:3005',
    },
    streaming: {
      name: 'streaming',
      url: process.env.STREAMING_SERVICE_URL || 'http://localhost:3006',
    },
    recommendations: {
      name: 'recommendations',
      url: process.env.RECOMMENDATIONS_SERVICE_URL || 'http://localhost:3007',
    },
    billing: {
      name: 'billing',
      url: process.env.BILLING_SERVICE_URL || 'http://localhost:3008',
    },
    analytics: {
      name: 'analytics',
      url: process.env.ANALYTICS_SERVICE_URL || 'http://localhost:3009',
    },
  },

  
  featureFlags: {
    enableHDR: process.env.FEATURE_HDR,
    enable4K: process.env.FEATURE_4K,
    enableLiveStreaming: process.env.FEATURE_LIVE,
  },

  rateLimit: {
    windowMs: 60000,
    
    max: process.env.RATE_LIMIT_MAX || '100',
  },
};

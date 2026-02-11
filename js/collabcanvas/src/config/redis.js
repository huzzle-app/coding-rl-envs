/**
 * Redis Configuration
 */

module.exports = {
  host: process.env.REDIS_HOST || 'localhost',
  port: process.env.REDIS_PORT || 6379,
  password: process.env.REDIS_PASSWORD || undefined,
  db: process.env.REDIS_DB || 0,

  // Connection options
  retryDelayOnFailover: 100,
  maxRetriesPerRequest: 3,
  enableReadyCheck: true,

  // Key prefixes
  prefix: {
    session: 'session:',
    presence: 'presence:',
    cursor: 'cursor:',
    board: 'board:',
    cache: 'cache:',
  },
};

module.exports = {
  port: process.env.PORT || 3007,
  databaseUrl: process.env.DATABASE_URL || 'postgres://datanexus:datanexus@localhost:5434/metrics_db',
  redisHost: process.env.REDIS_HOST || 'localhost',
  queryTimeout: 30000,
  maxResultSize: 100000,
};

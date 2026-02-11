module.exports = {
  port: process.env.PORT || 3014,
  databaseUrl: process.env.DATABASE_URL || 'postgres://datanexus:datanexus@localhost:5435/billing_db',
  redisHost: process.env.REDIS_HOST || 'localhost',
};

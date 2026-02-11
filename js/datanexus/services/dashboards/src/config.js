module.exports = {
  port: process.env.PORT || 3009,
  databaseUrl: process.env.DATABASE_URL || 'postgres://datanexus:datanexus@localhost:5432/pipeline_db',
  redisHost: process.env.REDIS_HOST || 'localhost',
};

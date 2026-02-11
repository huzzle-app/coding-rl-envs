module.exports = {
  port: process.env.PORT || 3013,
  databaseUrl: process.env.DATABASE_URL || 'postgres://datanexus:datanexus@localhost:5433/users_db',
  redisHost: process.env.REDIS_HOST || 'localhost',
  consulHost: process.env.CONSUL_HOST || 'localhost',
};

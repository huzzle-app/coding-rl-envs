module.exports = {
  port: process.env.PORT || 3001,
  jwtSecret: process.env.JWT_SECRET || 'default-secret',
  databaseUrl: process.env.DATABASE_URL || 'postgres://datanexus:datanexus@localhost:5433/users_db',
  redisHost: process.env.REDIS_HOST || 'localhost',
};

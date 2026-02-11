module.exports = {
  port: process.env.PORT || 3013,
  databaseUrl: process.env.DATABASE_URL,
  redisHost: process.env.REDIS_HOST || 'localhost',
  rabbitmqUrl: process.env.RABBITMQ_URL,
  rabbitmqPrefetch: process.env.RABBITMQ_PREFETCH || '10',
};

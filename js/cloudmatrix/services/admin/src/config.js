module.exports = {
  port: process.env.PORT || 3014,
  databaseUrl: process.env.DATABASE_URL,
  redisHost: process.env.REDIS_HOST || 'localhost',
  consulHost: process.env.CONSUL_HOST || 'localhost',
  rabbitmqUrl: process.env.RABBITMQ_URL,
};

module.exports = {
  port: process.env.PORT || 3005,
  rabbitmqUrl: process.env.RABBITMQ_URL || 'amqp://datanexus:datanexus@localhost',
  redisHost: process.env.REDIS_HOST || 'localhost',
  databaseUrl: process.env.DATABASE_URL || 'postgres://datanexus:datanexus@localhost:5434/metrics_db',
};

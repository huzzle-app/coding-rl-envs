module.exports = {
  port: process.env.PORT || 3012,
  rabbitmqUrl: process.env.RABBITMQ_URL || 'amqp://datanexus:datanexus@localhost',
  redisHost: process.env.REDIS_HOST || 'localhost',
  maxWorkers: 4,
};

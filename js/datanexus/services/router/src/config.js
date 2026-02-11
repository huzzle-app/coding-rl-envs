module.exports = {
  port: process.env.PORT || 3004,
  rabbitmqUrl: process.env.RABBITMQ_URL || 'amqp://datanexus:datanexus@localhost',
  consulHost: process.env.CONSUL_HOST || 'localhost',
  redisHost: process.env.REDIS_HOST || 'localhost',
};

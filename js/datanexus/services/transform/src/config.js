module.exports = {
  port: process.env.PORT || 3003,
  rabbitmqUrl: process.env.RABBITMQ_URL || 'amqp://datanexus:datanexus@localhost',
  redisHost: process.env.REDIS_HOST || 'localhost',
  maxUdfTimeout: 30000,
  maxTransformChainDepth: 50,
};

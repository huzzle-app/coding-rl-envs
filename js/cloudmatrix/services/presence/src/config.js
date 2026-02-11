module.exports = {
  port: process.env.PORT || 3004,
  redisHost: process.env.REDIS_HOST || 'localhost',
  rabbitmqUrl: process.env.RABBITMQ_URL,
  pingInterval: process.env.WS_PING_INTERVAL || '30000',
};

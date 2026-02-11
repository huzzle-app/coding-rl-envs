module.exports = {
  port: process.env.PORT || 3002,
  rabbitmqUrl: process.env.RABBITMQ_URL || 'amqp://datanexus:datanexus@localhost',
  redisHost: process.env.REDIS_HOST || 'localhost',
  databaseUrl: process.env.DATABASE_URL || 'postgres://datanexus:datanexus@localhost:5432/pipeline_db',
  maxBatchSize: 10000,
  maxPayloadSize: '50mb',
};

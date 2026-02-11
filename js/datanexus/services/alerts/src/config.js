module.exports = {
  port: process.env.PORT || 3008,
  rabbitmqUrl: process.env.RABBITMQ_URL || 'amqp://datanexus:datanexus@localhost',
  redisHost: process.env.REDIS_HOST || 'localhost',
  databaseUrl: process.env.DATABASE_URL || 'postgres://datanexus:datanexus@localhost:5432/pipeline_db',
  evaluationInterval: 10000,
  deduplicationWindow: 300000,
};

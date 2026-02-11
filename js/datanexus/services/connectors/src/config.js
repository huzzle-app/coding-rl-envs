module.exports = {
  port: process.env.PORT || 3010,
  rabbitmqUrl: process.env.RABBITMQ_URL || 'amqp://datanexus:datanexus@localhost',
  redisHost: process.env.REDIS_HOST || 'localhost',
  minioEndpoint: process.env.MINIO_ENDPOINT || 'localhost:9000',
  minioAccessKey: process.env.MINIO_ACCESS_KEY || 'datanexus',
  minioSecretKey: process.env.MINIO_SECRET_KEY || 'datanexus123',
};

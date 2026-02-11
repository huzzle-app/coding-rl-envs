module.exports = {
  port: process.env.PORT || 3009,
  minioEndpoint: process.env.MINIO_ENDPOINT || 'localhost:9000',
  minioAccessKey: process.env.MINIO_ACCESS_KEY,
  minioSecretKey: process.env.MINIO_SECRET_KEY,
  redisHost: process.env.REDIS_HOST || 'localhost',
  rabbitmqUrl: process.env.RABBITMQ_URL,
};

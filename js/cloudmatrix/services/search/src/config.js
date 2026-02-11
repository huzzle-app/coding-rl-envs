module.exports = {
  port: process.env.PORT || 3007,
  elasticsearchUrl: process.env.ELASTICSEARCH_URL || 'http://localhost:9200',
  redisHost: process.env.REDIS_HOST || 'localhost',
  rabbitmqUrl: process.env.RABBITMQ_URL,
  
  connectionTimeout: process.env.ES_TIMEOUT || '500',
};

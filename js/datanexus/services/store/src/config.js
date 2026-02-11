module.exports = {
  port: process.env.PORT || 3006,
  databaseUrl: process.env.DATABASE_URL || 'postgres://datanexus:datanexus@localhost:5434/metrics_db',
  redisHost: process.env.REDIS_HOST || 'localhost',
  minioEndpoint: process.env.MINIO_ENDPOINT || 'localhost:9000',
  retentionDays: 90,
  compactionInterval: 3600000,
};

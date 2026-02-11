/**
 * Permissions Service
 */

const express = require('express');
const app = express();
app.use(express.json());

const config = {
  port: process.env.PORT || 3012,
  databaseUrl: process.env.DATABASE_URL,
  redisHost: process.env.REDIS_HOST || 'localhost',
};

const { ACLService } = require('./services/acl');

app.get('/permissions/:documentId', async (req, res) => {
  try {
    const service = new ACLService();
    const permissions = await service.getPermissions(req.params.documentId, req.query.userId);
    res.json(permissions);
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

app.post('/permissions/:documentId/share', async (req, res) => {
  try {
    const { userId, role } = req.body;

    const service = new ACLService();
    const result = await service.shareDocument(req.params.documentId, userId, role);
    res.json(result);
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

app.get('/health', (req, res) => {
  res.json({ status: 'healthy' });
});

app.listen(config.port, () => {
  console.log(`Permissions service listening on port ${config.port}`);
});

module.exports = app;

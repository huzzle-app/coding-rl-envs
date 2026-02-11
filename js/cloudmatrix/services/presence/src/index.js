/**
 * Presence Service
 */

const express = require('express');
const http = require('http');

const app = express();
app.use(express.json());

const config = {
  port: process.env.PORT || 3004,
  redisHost: process.env.REDIS_HOST || 'localhost',
  
  pingInterval: process.env.WS_PING_INTERVAL || '30000',
};

const { PresenceService } = require('./services/presence');

app.get('/health', (req, res) => {
  res.json({ status: 'healthy' });
});

app.get('/presence/:documentId', async (req, res) => {
  const service = new PresenceService();
  const presence = await service.getPresence(req.params.documentId);
  res.json(presence);
});

const server = http.createServer(app);


async function startWebSocket() {
  const presenceService = new PresenceService();
  
  presenceService.initializeWebSocket(server);
}

startWebSocket();

server.listen(config.port, () => {
  console.log(`Presence service listening on port ${config.port}`);
});

module.exports = app;

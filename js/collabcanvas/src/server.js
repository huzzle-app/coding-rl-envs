/**
 * Server Setup
 *
 * BUG F3: Missing await on database sync
 */

const http = require('http');
const createApp = require('./app');
const setupWebSocket = require('./websocket');
const db = require('./models');
const Redis = require('ioredis');

// Services
const SyncService = require('./services/canvas/sync.service');
const HistoryService = require('./services/canvas/history.service');
const PresenceService = require('./services/collaboration/presence.service');
const BroadcastService = require('./services/collaboration/broadcast.service');
const PermissionService = require('./services/board/permission.service');
const JWTService = require('./services/auth/jwt.service');

async function startServer() {
  const app = createApp();
  const server = http.createServer(app);

  // Redis client
  const redis = new Redis({
    host: process.env.REDIS_HOST || 'localhost',
    port: process.env.REDIS_PORT || 6379,
  });

  // Initialize services
  const jwtService = new JWTService();
  const historyService = new HistoryService();
  const permissionService = new PermissionService(db);

  
  // This can cause "relation does not exist" errors on first requests
  db.sequelize.sync();

  // These services need the io instance
  const io = setupWebSocket(server, {});

  const syncService = new SyncService(io, {
    host: process.env.REDIS_HOST || 'localhost',
    port: process.env.REDIS_PORT || 6379,
  });
  const presenceService = new PresenceService(redis);
  const broadcastService = new BroadcastService(io, redis);

  // Initialize sync service
  await syncService.initialize();

  // Update WebSocket services
  io.services = {
    syncService,
    historyService,
    presenceService,
    broadcastService,
    permissionService,
    jwtService,
  };

  // Make services available to routes
  app.locals.services = io.services;
  app.locals.db = db;

  const port = process.env.PORT || 3000;
  server.listen(port, () => {
    console.log(`CollabCanvas server running on port ${port}`);
  });

  // Graceful shutdown
  process.on('SIGTERM', async () => {
    console.log('SIGTERM received, shutting down...');
    await syncService.close();
    await redis.quit();
    server.close(() => {
      console.log('Server closed');
      process.exit(0);
    });
  });

  return { app, server, io };
}

module.exports = startServer;

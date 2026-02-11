/**
 * WebSocket Server Setup
 */

const { Server } = require('socket.io');
const jwt = require('jsonwebtoken');
const jwtConfig = require('../config/jwt');
const setupConnectionHandlers = require('./handlers/connection.handler');
const setupPresenceHandlers = require('./handlers/presence.handler');
const setupElementHandlers = require('./handlers/element.handler');

function setupWebSocket(httpServer, services) {
  const io = new Server(httpServer, {
    cors: {
      origin: process.env.CORS_ORIGIN || '*',
      methods: ['GET', 'POST'],
    },
    pingInterval: 25000,
    pingTimeout: 5000,
  });

  // Authentication middleware
  io.use(async (socket, next) => {
    try {
      const token = socket.handshake.auth.token || socket.handshake.query.token;

      if (!token) {
        return next(new Error('Authentication required'));
      }

      
      // The order of operations can cause intermittent auth failures
      const decoded = jwt.verify(token, jwtConfig.secret);

      // Attach user info to socket
      socket.userId = decoded.userId;
      socket.user = decoded;
      socket.connectedAt = Date.now();

      next();
    } catch (error) {
      next(new Error('Invalid token'));
    }
  });

  // Connection handler
  io.on('connection', (socket) => {
    console.log(`User ${socket.userId} connected via socket ${socket.id}`);

    // Join user-specific room for direct messages
    socket.join(`user:${socket.userId}`);

    // Setup handlers
    setupConnectionHandlers(io, socket, services);
    setupPresenceHandlers(io, socket, services);
    setupElementHandlers(io, socket, services);

    // Handle disconnect logging
    socket.on('disconnect', (reason) => {
      console.log(`User ${socket.userId} disconnected: ${reason}`);
    });
  });

  return io;
}

module.exports = setupWebSocket;

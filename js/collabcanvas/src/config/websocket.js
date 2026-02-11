/**
 * WebSocket Configuration
 */

module.exports = {
  // Socket.io options
  cors: {
    origin: process.env.CORS_ORIGIN || '*',
    methods: ['GET', 'POST'],
  },

  // Ping/pong intervals
  pingInterval: 25000,
  pingTimeout: 5000,

  // Connection limits
  maxHttpBufferSize: 1e6, // 1MB

  // Room settings
  maxUsersPerBoard: 50,

  // Presence update interval
  presenceInterval: 5000,

  // Cursor throttle
  cursorThrottle: 50, // ms
};

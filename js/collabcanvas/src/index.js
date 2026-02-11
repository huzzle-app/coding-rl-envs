/**
 * CollabCanvas Entry Point
 */

require('dotenv').config();

const startServer = require('./server');

startServer().catch((error) => {
  console.error('Failed to start server:', error);
  process.exit(1);
});

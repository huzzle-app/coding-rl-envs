/**
 * CollabCanvas Configuration
 * BUG F2: Circular import - this file imports database.js which imports this file
 */


const database = require('./database');
const redis = require('./redis');
const jwt = require('./jwt');
const websocket = require('./websocket');

// Load environment variables
require('dotenv').config();

const config = {
  env: process.env.NODE_ENV || 'development',
  port: process.env.PORT || 3000,

  database,
  redis,
  jwt,
  websocket,

  // Upload settings
  upload: {
    maxFileSize: process.env.MAX_FILE_SIZE || 10 * 1024 * 1024, // 10MB
    allowedTypes: ['image/png', 'image/jpeg', 'image/gif', 'image/svg+xml'],
    uploadDir: process.env.UPLOAD_DIR || './uploads',
  },

  // Rate limiting
  rateLimit: {
    windowMs: 15 * 60 * 1000, // 15 minutes
    max: 100, // requests per window
  },
};

module.exports = config;

/**
 * Database Configuration
 * BUG F2: Circular import with config/index.js
 * BUG F4: Environment variable type coercion
 */


const config = require('./index');

module.exports = {
  host: process.env.DB_HOST || 'localhost',
  port: process.env.DB_PORT || 5432,
  database: process.env.DB_NAME || 'collabcanvas',
  username: process.env.DB_USER || 'collabcanvas',
  password: process.env.DB_PASSWORD || 'collabcanvas_dev',
  dialect: 'postgres',

  pool: {
    
    // '5' || 10 = '5' (string), causes Sequelize pool config errors
    max: process.env.DB_POOL_SIZE || 10,
    min: process.env.DB_POOL_MIN || 2,
    acquire: 30000,
    idle: 10000,
  },

  logging: process.env.NODE_ENV === 'development' ? console.log : false,

  define: {
    timestamps: true,
    underscored: true,
  },
};

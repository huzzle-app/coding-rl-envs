/**
 * Sequelize Model Loader
 */

const { Sequelize } = require('sequelize');
const dbConfig = require('../config/database');

const sequelize = new Sequelize(
  dbConfig.database,
  dbConfig.username,
  dbConfig.password,
  {
    host: dbConfig.host,
    port: dbConfig.port,
    dialect: dbConfig.dialect,
    pool: dbConfig.pool,
    logging: dbConfig.logging,
    define: dbConfig.define,
  }
);

const db = {
  sequelize,
  Sequelize,
};

// Import models
db.User = require('./User')(sequelize, Sequelize);
db.Team = require('./Team')(sequelize, Sequelize);
db.Board = require('./Board')(sequelize, Sequelize);
db.Element = require('./Element')(sequelize, Sequelize);
db.Comment = require('./Comment')(sequelize, Sequelize);
db.Attachment = require('./Attachment')(sequelize, Sequelize);
db.BoardMember = require('./BoardMember')(sequelize, Sequelize);
db.Session = require('./Session')(sequelize, Sequelize);

// Define associations
Object.keys(db).forEach((modelName) => {
  if (db[modelName].associate) {
    db[modelName].associate(db);
  }
});

module.exports = db;

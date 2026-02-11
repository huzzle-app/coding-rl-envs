/**
 * Session Model - Active user sessions for presence
 */

module.exports = (sequelize, DataTypes) => {
  const Session = sequelize.define('Session', {
    id: {
      type: DataTypes.UUID,
      defaultValue: DataTypes.UUIDV4,
      primaryKey: true,
    },
    userId: {
      type: DataTypes.UUID,
      allowNull: false,
      field: 'user_id',
    },
    boardId: {
      type: DataTypes.UUID,
      field: 'board_id',
    },
    socketId: {
      type: DataTypes.STRING(255),
      field: 'socket_id',
    },
    lastActivity: {
      type: DataTypes.DATE,
      defaultValue: DataTypes.NOW,
      field: 'last_activity',
    },
    cursorPosition: {
      type: DataTypes.JSONB,
      field: 'cursor_position',
    },
    selectedElements: {
      type: DataTypes.ARRAY(DataTypes.UUID),
      defaultValue: [],
      field: 'selected_elements',
    },
    metadata: {
      type: DataTypes.JSONB,
      defaultValue: {},
    },
  }, {
    tableName: 'sessions',
    indexes: [
      { fields: ['user_id'] },
      { fields: ['board_id'] },
      { fields: ['socket_id'] },
    ],
  });

  Session.associate = (models) => {
    Session.belongsTo(models.User, { foreignKey: 'user_id', as: 'user' });
    Session.belongsTo(models.Board, { foreignKey: 'board_id', as: 'board' });
  };

  return Session;
};

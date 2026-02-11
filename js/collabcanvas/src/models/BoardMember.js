/**
 * BoardMember Model - Board access permissions
 */

module.exports = (sequelize, DataTypes) => {
  const BoardMember = sequelize.define('BoardMember', {
    id: {
      type: DataTypes.UUID,
      defaultValue: DataTypes.UUIDV4,
      primaryKey: true,
    },
    boardId: {
      type: DataTypes.UUID,
      allowNull: false,
      field: 'board_id',
    },
    userId: {
      type: DataTypes.UUID,
      allowNull: false,
      field: 'user_id',
    },
    role: {
      type: DataTypes.ENUM('viewer', 'editor', 'admin'),
      defaultValue: 'viewer',
    },
    invitedBy: {
      type: DataTypes.UUID,
      field: 'invited_by',
    },
    invitedAt: {
      type: DataTypes.DATE,
      defaultValue: DataTypes.NOW,
      field: 'invited_at',
    },
  }, {
    tableName: 'board_members',
    indexes: [
      { fields: ['board_id', 'user_id'], unique: true },
      { fields: ['user_id'] },
    ],
  });

  BoardMember.associate = (models) => {
    BoardMember.belongsTo(models.Board, { foreignKey: 'board_id', as: 'board' });
    BoardMember.belongsTo(models.User, { foreignKey: 'user_id', as: 'user' });
    BoardMember.belongsTo(models.User, { foreignKey: 'invited_by', as: 'inviter' });
  };

  // Role hierarchy for permission checks
  BoardMember.ROLE_LEVELS = {
    viewer: 1,
    editor: 2,
    admin: 3,
  };

  BoardMember.hasPermission = function(userRole, requiredRole) {
    const userLevel = this.ROLE_LEVELS[userRole] || 0;
    const requiredLevel = this.ROLE_LEVELS[requiredRole] || 0;
    return userLevel >= requiredLevel;
  };

  return BoardMember;
};

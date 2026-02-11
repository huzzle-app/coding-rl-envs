/**
 * Comment Model - Annotations on boards or elements
 */

module.exports = (sequelize, DataTypes) => {
  const Comment = sequelize.define('Comment', {
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
    elementId: {
      type: DataTypes.UUID,
      field: 'element_id',
    },
    userId: {
      type: DataTypes.UUID,
      allowNull: false,
      field: 'user_id',
    },
    parentId: {
      type: DataTypes.UUID,
      field: 'parent_id',
    },
    content: {
      type: DataTypes.TEXT,
      allowNull: false,
    },
    x: {
      type: DataTypes.FLOAT,
      comment: 'Position on canvas for board-level comments',
    },
    y: {
      type: DataTypes.FLOAT,
    },
    isResolved: {
      type: DataTypes.BOOLEAN,
      defaultValue: false,
      field: 'is_resolved',
    },
    resolvedBy: {
      type: DataTypes.UUID,
      field: 'resolved_by',
    },
    resolvedAt: {
      type: DataTypes.DATE,
      field: 'resolved_at',
    },
  }, {
    tableName: 'comments',
    indexes: [
      { fields: ['board_id'] },
      { fields: ['element_id'] },
      { fields: ['user_id'] },
      { fields: ['parent_id'] },
    ],
  });

  Comment.associate = (models) => {
    Comment.belongsTo(models.Board, { foreignKey: 'board_id', as: 'board' });
    Comment.belongsTo(models.Element, { foreignKey: 'element_id', as: 'element' });
    Comment.belongsTo(models.User, { foreignKey: 'user_id', as: 'author' });
    Comment.belongsTo(Comment, { foreignKey: 'parent_id', as: 'parent' });
    Comment.hasMany(Comment, { foreignKey: 'parent_id', as: 'replies' });
    Comment.belongsTo(models.User, { foreignKey: 'resolved_by', as: 'resolver' });
  };

  return Comment;
};

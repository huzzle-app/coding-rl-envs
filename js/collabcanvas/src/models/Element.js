/**
 * Element Model - Canvas elements (shapes, text, images, etc.)
 */

module.exports = (sequelize, DataTypes) => {
  const Element = sequelize.define('Element', {
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
    type: {
      type: DataTypes.ENUM('rectangle', 'ellipse', 'line', 'arrow', 'text', 'image', 'sticky', 'freehand'),
      allowNull: false,
    },
    x: {
      type: DataTypes.FLOAT,
      allowNull: false,
      defaultValue: 0,
    },
    y: {
      type: DataTypes.FLOAT,
      allowNull: false,
      defaultValue: 0,
    },
    width: {
      type: DataTypes.FLOAT,
      defaultValue: 100,
    },
    height: {
      type: DataTypes.FLOAT,
      defaultValue: 100,
    },
    rotation: {
      type: DataTypes.FLOAT,
      defaultValue: 0,
    },
    zIndex: {
      type: DataTypes.INTEGER,
      defaultValue: 0,
      field: 'z_index',
    },
    properties: {
      type: DataTypes.JSONB,
      defaultValue: {},
      comment: 'Type-specific properties (fill, stroke, text content, etc.)',
    },
    createdBy: {
      type: DataTypes.UUID,
      field: 'created_by',
    },
    lockedBy: {
      type: DataTypes.UUID,
      field: 'locked_by',
    },
    lockedAt: {
      type: DataTypes.DATE,
      field: 'locked_at',
    },
    version: {
      type: DataTypes.INTEGER,
      defaultValue: 1,
    },
  }, {
    tableName: 'elements',
    indexes: [
      { fields: ['board_id'] },
      { fields: ['created_by'] },
      { fields: ['z_index'] },
    ],
  });

  Element.associate = (models) => {
    Element.belongsTo(models.Board, { foreignKey: 'board_id', as: 'board' });
    Element.belongsTo(models.User, { foreignKey: 'created_by', as: 'creator' });
    Element.belongsTo(models.User, { foreignKey: 'locked_by', as: 'locker' });
    Element.hasMany(models.Comment, { foreignKey: 'element_id', as: 'comments' });
  };

  return Element;
};

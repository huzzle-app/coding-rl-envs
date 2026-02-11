/**
 * Board Model
 */

module.exports = (sequelize, DataTypes) => {
  const Board = sequelize.define('Board', {
    id: {
      type: DataTypes.UUID,
      defaultValue: DataTypes.UUIDV4,
      primaryKey: true,
    },
    name: {
      type: DataTypes.STRING(255),
      allowNull: false,
    },
    slug: {
      type: DataTypes.STRING(255),
      allowNull: false,
    },
    description: {
      type: DataTypes.TEXT,
    },
    teamId: {
      type: DataTypes.UUID,
      field: 'team_id',
    },
    ownerId: {
      type: DataTypes.UUID,
      allowNull: false,
      field: 'owner_id',
    },
    isPublic: {
      type: DataTypes.BOOLEAN,
      defaultValue: false,
      field: 'is_public',
    },
    thumbnail: {
      type: DataTypes.TEXT,
    },
    settings: {
      type: DataTypes.JSONB,
      defaultValue: {
        backgroundColor: '#ffffff',
        gridEnabled: false,
        gridSize: 20,
      },
    },
    canvasState: {
      type: DataTypes.JSONB,
      defaultValue: {
        version: 1,
        elements: [],
        viewport: { x: 0, y: 0, zoom: 1 },
      },
      field: 'canvas_state',
    },
  }, {
    tableName: 'boards',
    indexes: [
      { fields: ['team_id'] },
      { fields: ['owner_id'] },
      { fields: ['slug', 'team_id'], unique: true },
    ],
    hooks: {
      beforeCreate: (board) => {
        if (!board.slug) {
          board.slug = board.name
            .toLowerCase()
            .replace(/[^a-z0-9]+/g, '-')
            .replace(/^-|-$/g, '');
        }
      },
    },
  });

  Board.associate = (models) => {
    Board.belongsTo(models.Team, { foreignKey: 'team_id', as: 'team' });
    Board.belongsTo(models.User, { foreignKey: 'owner_id', as: 'owner' });
    Board.belongsToMany(models.User, {
      through: models.BoardMember,
      foreignKey: 'board_id',
      as: 'members',
    });
    Board.hasMany(models.Element, { foreignKey: 'board_id', as: 'elements' });
    Board.hasMany(models.Comment, { foreignKey: 'board_id', as: 'comments' });
    Board.hasMany(models.Attachment, { foreignKey: 'board_id', as: 'attachments' });
  };

  return Board;
};

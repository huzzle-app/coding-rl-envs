/**
 * Attachment Model - File attachments on boards
 */

module.exports = (sequelize, DataTypes) => {
  const Attachment = sequelize.define('Attachment', {
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
    uploadedBy: {
      type: DataTypes.UUID,
      allowNull: false,
      field: 'uploaded_by',
    },
    filename: {
      type: DataTypes.STRING(255),
      allowNull: false,
    },
    originalFilename: {
      type: DataTypes.STRING(255),
      allowNull: false,
      field: 'original_filename',
    },
    mimeType: {
      type: DataTypes.STRING(100),
      allowNull: false,
      field: 'mime_type',
    },
    size: {
      type: DataTypes.INTEGER,
      allowNull: false,
    },
    path: {
      type: DataTypes.TEXT,
      allowNull: false,
    },
    url: {
      type: DataTypes.TEXT,
    },
    thumbnailUrl: {
      type: DataTypes.TEXT,
      field: 'thumbnail_url',
    },
    metadata: {
      type: DataTypes.JSONB,
      defaultValue: {},
    },
  }, {
    tableName: 'attachments',
    indexes: [
      { fields: ['board_id'] },
      { fields: ['uploaded_by'] },
    ],
  });

  Attachment.associate = (models) => {
    Attachment.belongsTo(models.Board, { foreignKey: 'board_id', as: 'board' });
    Attachment.belongsTo(models.User, { foreignKey: 'uploaded_by', as: 'uploader' });
  };

  return Attachment;
};

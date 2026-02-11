/**
 * Team Model
 */

module.exports = (sequelize, DataTypes) => {
  const Team = sequelize.define('Team', {
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
      unique: true,
    },
    description: {
      type: DataTypes.TEXT,
    },
    avatarUrl: {
      type: DataTypes.TEXT,
      field: 'avatar_url',
    },
    ownerId: {
      type: DataTypes.UUID,
      allowNull: false,
      field: 'owner_id',
    },
    settings: {
      type: DataTypes.JSONB,
      defaultValue: {},
    },
  }, {
    tableName: 'teams',
    hooks: {
      beforeCreate: (team) => {
        if (!team.slug) {
          team.slug = team.name
            .toLowerCase()
            .replace(/[^a-z0-9]+/g, '-')
            .replace(/^-|-$/g, '');
        }
      },
    },
  });

  Team.associate = (models) => {
    Team.belongsTo(models.User, { foreignKey: 'owner_id', as: 'owner' });
    Team.belongsToMany(models.User, {
      through: 'team_members',
      foreignKey: 'team_id',
      as: 'members',
    });
    Team.hasMany(models.Board, { foreignKey: 'team_id', as: 'boards' });
  };

  return Team;
};

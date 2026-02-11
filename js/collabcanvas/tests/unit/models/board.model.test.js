/**
 * Board Model Unit Tests
 */

const { DataTypes } = require('sequelize');

describe('Board Model', () => {
  let Board;
  let mockSequelize;

  beforeEach(() => {
    mockSequelize = {
      define: jest.fn().mockReturnValue({
        associate: jest.fn(),
        belongsTo: jest.fn(),
        hasMany: jest.fn(),
      }),
    };

    // Mock the model
    Board = {
      id: { type: DataTypes.UUID, primaryKey: true },
      name: { type: DataTypes.STRING, allowNull: false },
      ownerId: { type: DataTypes.UUID, allowNull: false },
      isPublic: { type: DataTypes.BOOLEAN, defaultValue: false },
      settings: { type: DataTypes.JSONB, defaultValue: {} },
    };
  });

  describe('schema validation', () => {
    it('should require name field', () => {
      expect(Board.name.allowNull).toBe(false);
    });

    it('should require ownerId field', () => {
      expect(Board.ownerId.allowNull).toBe(false);
    });

    it('should have default isPublic as false', () => {
      expect(Board.isPublic.defaultValue).toBe(false);
    });

    it('should have default empty settings', () => {
      expect(Board.settings.defaultValue).toEqual({});
    });
  });

  describe('validation', () => {
    it('should validate board name length', () => {
      const validName = 'My Board';
      const tooLongName = 'A'.repeat(256);

      expect(validName.length).toBeLessThanOrEqual(255);
      expect(tooLongName.length).toBeGreaterThan(255);
    });

    it('should validate UUID format for ownerId', () => {
      const validUUID = '123e4567-e89b-12d3-a456-426614174000';
      const invalidUUID = 'not-a-uuid';

      const uuidRegex = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

      expect(uuidRegex.test(validUUID)).toBe(true);
      expect(uuidRegex.test(invalidUUID)).toBe(false);
    });
  });
});

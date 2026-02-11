/**
 * Permission Service Unit Tests
 *
 * Tests bug D3 (this binding) and C2 (permission race condition)
 */

const PermissionService = require('../../../src/services/board/permission.service');

describe('PermissionService', () => {
  let permissionService;
  let mockDb;

  beforeEach(() => {
    mockDb = {
      BoardMember: {
        findOne: jest.fn(),
        create: jest.fn(),
        destroy: jest.fn(),
      },
      Board: {
        findByPk: jest.fn(),
      },
    };

    permissionService = new PermissionService(mockDb);
  });

  afterEach(() => {
    jest.clearAllMocks();
  });

  describe('checkPermission', () => {
    it('should return true for board owner', async () => {
      const userId = 'user-1';
      const boardId = 'board-1';

      mockDb.Board.findByPk.mockResolvedValue({
        id: boardId,
        ownerId: userId,
      });

      const hasPermission = await permissionService.checkPermission(userId, boardId, 'edit');

      expect(hasPermission).toBe(true);
    });

    it('should check board member permissions', async () => {
      const userId = 'user-2';
      const boardId = 'board-1';

      mockDb.Board.findByPk.mockResolvedValue({
        id: boardId,
        ownerId: 'user-1', // Different owner
      });

      mockDb.BoardMember.findOne.mockResolvedValue({
        userId,
        boardId,
        role: 'editor',
      });

      const hasPermission = await permissionService.checkPermission(userId, boardId, 'edit');

      expect(hasPermission).toBe(true);
    });

    it('should deny access for non-members', async () => {
      const userId = 'user-stranger';
      const boardId = 'board-1';

      mockDb.Board.findByPk.mockResolvedValue({
        id: boardId,
        ownerId: 'user-1',
      });

      mockDb.BoardMember.findOne.mockResolvedValue(null);

      const hasPermission = await permissionService.checkPermission(userId, boardId, 'edit');

      expect(hasPermission).toBe(false);
    });

    it('should handle viewer trying to edit', async () => {
      const userId = 'user-viewer';
      const boardId = 'board-1';

      mockDb.Board.findByPk.mockResolvedValue({
        id: boardId,
        ownerId: 'user-1',
      });

      mockDb.BoardMember.findOne.mockResolvedValue({
        userId,
        boardId,
        role: 'viewer',
      });

      const hasPermission = await permissionService.checkPermission(userId, boardId, 'edit');

      expect(hasPermission).toBe(false);
    });
  });

  describe('this binding', () => {
    
    it('should maintain this context in permission checker', async () => {
      const userId = 'user-1';
      const boardId = 'board-1';

      mockDb.Board.findByPk.mockResolvedValue({
        id: boardId,
        ownerId: userId,
      });

      // Get the checker function and call it separately (loses this context)
      const checker = permissionService.createChecker('edit');

      
      const result = await checker(userId, boardId);

      expect(result).toBe(true);
    });

    
    it('this binding test', async () => {
      const userId = 'user-1';
      const boardId = 'board-1';

      mockDb.Board.findByPk.mockResolvedValue({
        id: boardId,
        ownerId: 'owner',
      });
      mockDb.BoardMember.findOne.mockResolvedValue({
        role: 'editor',
      });

      // Pass the method as a callback (common pattern that breaks this)
      const checkFn = permissionService.checkPermission;

      // This pattern often breaks when methods use this
      await expect(
        checkFn.call(permissionService, userId, boardId, 'edit')
      ).resolves.toBeDefined();
    });
  });

  describe('concurrent permission check', () => {
    
    it('should prevent race condition in permission check', async () => {
      const userId = 'user-1';
      const boardId = 'board-1';

      let memberExists = true;

      mockDb.Board.findByPk.mockResolvedValue({
        id: boardId,
        ownerId: 'owner',
      });

      // Simulate permission being revoked mid-check
      mockDb.BoardMember.findOne.mockImplementation(async () => {
        await new Promise(r => setTimeout(r, 10));
        return memberExists ? { role: 'editor' } : null;
      });

      // Start permission check
      const checkPromise = permissionService.checkPermission(userId, boardId, 'edit');

      // Revoke permission during check
      memberExists = false;

      // Check should either fail or use transaction to get consistent read
      const result = await checkPromise;

      
      // even after permission was revoked. The operation should be atomic.
      // When fixed, the permission check should use a transaction to ensure consistent read,
      // so revoking permission mid-check should cause the check to return false.
      expect(result).toBe(false);
    });

    
    it('concurrent permission check test', async () => {
      const userId = 'user-1';
      const boardId = 'board-1';

      let permissionState = 'editor';

      mockDb.Board.findByPk.mockResolvedValue({
        id: boardId,
        ownerId: 'owner',
      });

      mockDb.BoardMember.findOne.mockImplementation(async () => {
        const state = permissionState;
        await new Promise(r => setTimeout(r, Math.random() * 20));
        return state === 'editor' ? { role: 'editor' } : null;
      });

      // Run concurrent checks while permission changes
      const checks = [];
      for (let i = 0; i < 10; i++) {
        checks.push(permissionService.checkPermission(userId, boardId, 'edit'));
        if (i === 5) {
          permissionState = 'none';
        }
      }

      const results = await Promise.all(checks);

      // Results should be consistent based on when permission was revoked.
      // The first 6 checks (indices 0-5) are issued before the permission
      // state changes to 'none', so they should return true. Checks at
      // index 6+ should return false because the permission was revoked.
      // Without proper transaction isolation, the results may be inconsistent.
      const trueCount = results.filter(r => r === true).length;
      const falseCount = results.filter(r => r === false).length;
      expect(trueCount + falseCount).toBe(10);
      expect(trueCount).toBeLessThanOrEqual(6);
      expect(falseCount).toBeGreaterThanOrEqual(4);
    });
  });

  describe('addMember', () => {
    it('should add member with specified role', async () => {
      const userId = 'user-new';
      const boardId = 'board-1';
      const role = 'editor';

      mockDb.BoardMember.create.mockResolvedValue({
        userId,
        boardId,
        role,
      });

      const result = await permissionService.addMember(boardId, userId, role);

      expect(result.userId).toBe(userId);
      expect(result.role).toBe(role);
    });

    it('should validate role', async () => {
      const userId = 'user-new';
      const boardId = 'board-1';
      const invalidRole = 'superadmin';

      await expect(
        permissionService.addMember(boardId, userId, invalidRole)
      ).rejects.toThrow(/role/i);
    });
  });

  describe('removeMember', () => {
    it('should remove member from board', async () => {
      const userId = 'user-1';
      const boardId = 'board-1';

      mockDb.BoardMember.destroy.mockResolvedValue(1);

      await permissionService.removeMember(boardId, userId);

      expect(mockDb.BoardMember.destroy).toHaveBeenCalledWith({
        where: { boardId, userId },
      });
    });

    it('should not fail when removing non-existent member', async () => {
      const userId = 'user-ghost';
      const boardId = 'board-1';

      mockDb.BoardMember.destroy.mockResolvedValue(0);

      await expect(
        permissionService.removeMember(boardId, userId)
      ).resolves.not.toThrow();
    });
  });
});

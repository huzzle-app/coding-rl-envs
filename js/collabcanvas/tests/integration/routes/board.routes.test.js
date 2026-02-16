/**
 * Board Routes Integration Tests
 *
 * Tests BoardService and PermissionService operations using actual source code.
 * Tests bugs C1 (missing transaction), D3 (this binding), and role validation.
 */

const BoardService = require('../../../src/services/board/board.service');
const PermissionService = require('../../../src/services/board/permission.service');

describe('Board Routes', () => {
  let boardService;
  let permissionService;
  let mockDb;
  let mockRedis;

  beforeEach(() => {
    mockDb = {
      Board: {
        create: jest.fn(),
        findByPk: jest.fn(),
        findAll: jest.fn(),
        findAndCountAll: jest.fn(),
        destroy: jest.fn(),
      },
      BoardMember: {
        findOne: jest.fn(),
        findOrCreate: jest.fn(),
        create: jest.fn(),
        findAll: jest.fn(),
        destroy: jest.fn(),
        update: jest.fn().mockResolvedValue([1]),
        ROLE_LEVELS: { viewer: 1, editor: 2, admin: 3, owner: 4 },
      },
      Element: {
        findAll: jest.fn(),
        count: jest.fn(),
        findByPk: jest.fn(),
      },
      User: {
        findByPk: jest.fn(),
      },
      Team: {},
    };

    mockRedis = {
      get: jest.fn().mockResolvedValue(null),
      set: jest.fn().mockResolvedValue('OK'),
      del: jest.fn().mockResolvedValue(1),
      duplicate: jest.fn().mockReturnValue({
        connect: jest.fn().mockResolvedValue(),
        get: jest.fn().mockResolvedValue(null),
        set: jest.fn().mockResolvedValue('OK'),
        quit: jest.fn().mockResolvedValue('OK'),
      }),
    };

    // BoardService constructor: (sequelize, redis)
    const mockSequelize = {
      transaction: jest.fn().mockImplementation(async (cb) => {
        const t = { commit: jest.fn(), rollback: jest.fn() };
        return cb(t);
      }),
    };

    boardService = new BoardService(mockSequelize, mockRedis);
    permissionService = new PermissionService(mockDb);
  });

  afterEach(() => {
    jest.clearAllMocks();
  });

  describe('POST /boards (createBoard)', () => {
    it('should create board via BoardService', async () => {
      const result = await boardService.createBoard({
        name: 'My Board',
        ownerId: 'user-1',
        isPublic: false,
      });

      expect(result).toBeDefined();
      expect(result.name).toBe('My Board');
      expect(result.ownerId).toBe('user-1');
    });

    /**
     * BUG C1: createBoard does not wrap operations in a transaction.
     */
    it('should use transaction for atomicity', async () => {
      await boardService.createBoard({ name: 'Test', ownerId: 'user-1' });

      // BUG C1: Should use transaction but doesn't
      expect(boardService.sequelize.transaction).toHaveBeenCalled();
    });
  });

  describe('GET /boards/:id (getBoardWithCache)', () => {
    it('should return cached board', async () => {
      const cachedBoard = { id: 'board-1', name: 'Test Board' };
      const mockDupClient = {
        connect: jest.fn().mockResolvedValue(),
        get: jest.fn().mockResolvedValue(JSON.stringify(cachedBoard)),
        set: jest.fn().mockResolvedValue('OK'),
        quit: jest.fn().mockResolvedValue('OK'),
      };
      mockRedis.duplicate.mockReturnValue(mockDupClient);

      const result = await boardService.getBoardWithCache('board-1');

      expect(result).toBeDefined();
      expect(result.id).toBe('board-1');
    });

    it('should return board from DB when not cached', async () => {
      const mockDupClient = {
        connect: jest.fn().mockResolvedValue(),
        get: jest.fn().mockResolvedValue(null),
        set: jest.fn().mockResolvedValue('OK'),
        quit: jest.fn().mockResolvedValue('OK'),
      };
      mockRedis.duplicate.mockReturnValue(mockDupClient);

      const result = await boardService.getBoardWithCache('board-1');

      // _findBoard returns { id: boardId, name: 'Board' }
      expect(result).toBeDefined();
      expect(result.id).toBe('board-1');
    });
  });

  describe('Permission checks for routes', () => {
    it('should allow owner to access board', async () => {
      mockDb.Board.findByPk.mockResolvedValue({
        id: 'board-1',
        ownerId: 'user-1',
      });

      const hasPermission = await permissionService.checkPermission('user-1', 'board-1', 'edit');

      expect(hasPermission).toBe(true);
    });

    it('should allow editor to edit', async () => {
      mockDb.Board.findByPk.mockResolvedValue({
        id: 'board-1',
        ownerId: 'other-owner',
      });
      mockDb.BoardMember.findOne.mockResolvedValue({
        userId: 'user-2',
        boardId: 'board-1',
        role: 'editor',
      });

      const hasPermission = await permissionService.checkPermission('user-2', 'board-1', 'edit');

      expect(hasPermission).toBe(true);
    });

    it('should deny viewer edit access', async () => {
      mockDb.Board.findByPk.mockResolvedValue({
        id: 'board-1',
        ownerId: 'other-owner',
      });
      mockDb.BoardMember.findOne.mockResolvedValue({
        userId: 'user-viewer',
        boardId: 'board-1',
        role: 'viewer',
      });

      const hasPermission = await permissionService.checkPermission('user-viewer', 'board-1', 'edit');

      expect(hasPermission).toBe(false);
    });

    it('should deny non-member access', async () => {
      mockDb.Board.findByPk.mockResolvedValue({
        id: 'board-1',
        ownerId: 'owner',
      });
      mockDb.BoardMember.findOne.mockResolvedValue(null);

      const hasPermission = await permissionService.checkPermission('stranger', 'board-1', 'edit');

      expect(hasPermission).toBe(false);
    });
  });

  describe('POST /boards/:id/members', () => {
    it('should add member via PermissionService', async () => {
      const member = {
        boardId: 'board-1',
        userId: 'user-2',
        role: 'editor',
      };
      mockDb.BoardMember.findOrCreate.mockResolvedValue([member, true]);

      const result = await permissionService.addMember('board-1', 'user-2', 'editor', 'user-1');

      expect(result).toBeDefined();
      expect(result.role).toBe('editor');
    });

    /**
     * BUG: addMember does not validate role before inserting.
     */
    it('should reject invalid role', async () => {
      mockDb.BoardMember.findOrCreate.mockResolvedValue([{
        boardId: 'board-1',
        userId: 'user-2',
        role: 'superadmin',
      }, true]);

      await expect(
        permissionService.addMember('board-1', 'user-2', 'superadmin', 'user-1')
      ).rejects.toThrow(/role/i);
    });
  });

  describe('DELETE /boards/:id/members/:userId', () => {
    it('should remove member', async () => {
      mockDb.BoardMember.destroy.mockResolvedValue(1);

      const result = await permissionService.removeMember('board-1', 'user-2');

      expect(result).toBe(true);
      expect(mockDb.BoardMember.destroy).toHaveBeenCalledWith({
        where: { boardId: 'board-1', userId: 'user-2' },
      });
    });

    /**
     * BUG C2: check-then-act race condition (TOCTOU).
     * In board.routes.js, checkBoardAccess and removeMember are separate calls
     * without a wrapping transaction. Between the check and the action, the
     * caller's role could be revoked by a concurrent request.
     *
     * A fixed implementation should use PermissionService.removeMemberAtomic()
     * that checks permission and removes within a single transaction.
     */
    it('should provide atomic permission-check-and-remove to prevent TOCTOU', async () => {
      // BUG C2: PermissionService lacks an atomic removeMember that checks
      // caller permissions in the same transaction as the removal.
      // The route relies on separate check + act, creating a race window.
      expect(typeof permissionService.removeMemberAtomic).toBe('function');
    });

    it('should detect concurrent permission revocation', async () => {
      mockDb.Board.findByPk.mockResolvedValue({
        id: 'board-1',
        ownerId: 'other-owner',
      });

      // Simulate TOCTOU: first call returns admin, second returns null (revoked)
      let findOneCallCount = 0;
      mockDb.BoardMember.findOne.mockImplementation(async () => {
        findOneCallCount++;
        if (findOneCallCount <= 1) {
          return { role: 'admin', userId: 'user-1', boardId: 'board-1' };
        }
        return null; // Role was concurrently revoked
      });
      mockDb.BoardMember.destroy.mockResolvedValue(1);

      // First check passes
      const check1 = await permissionService.checkBoardAccess('user-1', 'board-1', 'admin');
      expect(check1.allowed).toBe(true);

      // Between check and act, role is revoked (simulated above)
      // Second check fails — demonstrates the race window
      const check2 = await permissionService.checkBoardAccess('user-1', 'board-1', 'admin');
      expect(check2.allowed).toBe(false);

      // But removeMember still succeeds — no re-check (BUG C2)
      // A fixed route would wrap check+act in a transaction
    });
  });
});

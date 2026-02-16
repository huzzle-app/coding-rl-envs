/**
 * Board Model Unit Tests
 *
 * Tests BoardService operations using actual source code.
 * Tests bugs C1 (missing transaction), C3 (connection leak), C4 (N+1 queries)
 */

const BoardService = require('../../../src/services/board/board.service');

describe('Board Model and Service', () => {
  let boardService;
  let mockRedis;

  beforeEach(() => {
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
    // this.sequelize stores the first arg, this.redis stores the second
    const mockSequelize = {
      transaction: jest.fn().mockImplementation(async (cb) => {
        const t = { commit: jest.fn(), rollback: jest.fn() };
        return cb(t);
      }),
    };

    boardService = new BoardService(mockSequelize, mockRedis);
  });

  afterEach(() => {
    jest.clearAllMocks();
  });

  describe('createBoard', () => {
    /**
     * BUG C1: createBoard does not use transaction — partial failure
     * leaves orphan records.
     */
    it('should use transaction for board creation', async () => {
      const boardData = {
        name: 'Test Board',
        ownerId: 'user-1',
        isPublic: false,
      };

      const result = await boardService.createBoard(boardData);

      expect(result).toBeDefined();
      expect(result.name).toBe('Test Board');
      // BUG C1: Should use transaction but doesn't
      // createBoard should call this.sequelize.transaction()
      expect(boardService.sequelize.transaction).toHaveBeenCalled();
    });

    it('should create board with required fields', async () => {
      const boardData = {
        name: 'My Board',
        ownerId: 'user-1',
      };

      const result = await boardService.createBoard(boardData);

      expect(result).toBeDefined();
      expect(result.name).toBe('My Board');
      expect(result.ownerId).toBe('user-1');
      expect(result.id).toBeDefined();
    });

    it('should include default settings when none provided', async () => {
      const result = await boardService.createBoard({
        name: 'Board',
        ownerId: 'user-1',
      });

      expect(result.settings).toBeDefined();
    });
  });

  describe('getBoardWithCache', () => {
    it('should return cached board when available', async () => {
      const cachedBoard = { id: 'board-1', name: 'Cached Board' };
      const mockDupClient = {
        connect: jest.fn().mockResolvedValue(),
        get: jest.fn().mockResolvedValue(JSON.stringify(cachedBoard)),
        set: jest.fn().mockResolvedValue('OK'),
        quit: jest.fn().mockResolvedValue('OK'),
      };
      mockRedis.duplicate.mockReturnValue(mockDupClient);

      const result = await boardService.getBoardWithCache('board-1');

      expect(result).toEqual(cachedBoard);
      expect(mockDupClient.get).toHaveBeenCalledWith('board:board-1');
    });

    it('should fetch and cache board when not in cache', async () => {
      const mockDupClient = {
        connect: jest.fn().mockResolvedValue(),
        get: jest.fn().mockResolvedValue(null),
        set: jest.fn().mockResolvedValue('OK'),
        quit: jest.fn().mockResolvedValue('OK'),
      };
      mockRedis.duplicate.mockReturnValue(mockDupClient);

      const result = await boardService.getBoardWithCache('board-1');

      expect(result).toBeDefined();
      expect(mockDupClient.set).toHaveBeenCalledWith(
        'board:board-1',
        expect.any(String)
      );
    });

    /**
     * BUG C3: client.duplicate() connection not closed — resource leak.
     */
    it('should close duplicated Redis connections', async () => {
      const mockDupClient = {
        connect: jest.fn().mockResolvedValue(),
        get: jest.fn().mockResolvedValue(JSON.stringify({ id: 'board-1', name: 'Cached' })),
        set: jest.fn().mockResolvedValue('OK'),
        quit: jest.fn().mockResolvedValue('OK'),
      };
      mockRedis.duplicate.mockReturnValue(mockDupClient);

      await boardService.getBoardWithCache('board-1');

      // BUG C3: quit() should be called on duplicated client
      expect(mockDupClient.quit).toHaveBeenCalled();
    });
  });

  describe('getBoardsWithDetails', () => {
    /**
     * BUG C4: N+1 query — each board triggers separate element and member queries.
     * A fixed implementation would batch-load via _findElementsBatch/_findMembersBatch.
     */
    it('should batch-load elements and members instead of N+1 queries', async () => {
      const findElementsSpy = jest.spyOn(boardService, '_findElements');
      const findMembersSpy = jest.spyOn(boardService, '_findMembers');

      const result = await boardService.getBoardsWithDetails('user-1');

      expect(result).toBeDefined();
      expect(Array.isArray(result)).toBe(true);
      expect(result.length).toBeGreaterThan(1);

      // BUG C4: _findElements and _findMembers are called once per board (N times).
      // A fixed version would call a batch method once for all boards.
      // _findBoards returns 2 boards, so currently each spy is called 2x instead of 1x.
      expect(findElementsSpy).toHaveBeenCalledTimes(1);
      expect(findMembersSpy).toHaveBeenCalledTimes(1);

      findElementsSpy.mockRestore();
      findMembersSpy.mockRestore();
    });
  });
});

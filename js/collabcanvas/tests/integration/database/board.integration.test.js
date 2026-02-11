/**
 * Board Database Integration Tests
 *
 * Tests bugs C1 (missing transaction), C3 (Redis leak), C4 (N+1 query)
 */

describe('Board Database Integration', () => {
  let mockSequelize;
  let mockRedis;
  let BoardService;

  beforeEach(() => {
    mockSequelize = {
      transaction: jest.fn().mockImplementation(async (callback) => {
        const t = { commit: jest.fn(), rollback: jest.fn() };
        try {
          const result = await callback(t);
          await t.commit();
          return result;
        } catch (error) {
          await t.rollback();
          throw error;
        }
      }),
    };

    mockRedis = {
      get: jest.fn(),
      set: jest.fn().mockResolvedValue('OK'),
      del: jest.fn().mockResolvedValue(1),
      quit: jest.fn().mockResolvedValue('OK'),
      duplicate: jest.fn().mockReturnThis(),
      connect: jest.fn().mockResolvedValue(undefined),
    };

    BoardService = require('../../../src/services/board/board.service');
  });

  afterEach(() => {
    jest.clearAllMocks();
  });

  describe('createBoard', () => {
    
    it('should create board atomically', async () => {
      const boardService = new BoardService(mockSequelize, mockRedis);

      const boardData = {
        name: 'Test Board',
        ownerId: 'user-1',
        settings: { backgroundColor: '#ffffff' },
      };

      let transactionUsed = false;
      mockSequelize.transaction.mockImplementation(async (callback) => {
        transactionUsed = true;
        const t = { commit: jest.fn(), rollback: jest.fn() };
        return callback(t);
      });

      await boardService.createBoard(boardData);

      
      expect(transactionUsed).toBe(true);
    });

    
    it('transaction rollback test', async () => {
      const boardService = new BoardService(mockSequelize, mockRedis);

      const boardData = {
        name: 'Test Board',
        ownerId: 'user-1',
      };

      let rolledBack = false;
      mockSequelize.transaction.mockImplementation(async (callback) => {
        const t = {
          commit: jest.fn(),
          rollback: jest.fn(() => { rolledBack = true; }),
        };
        try {
          await callback(t);
          await t.commit();
        } catch (error) {
          await t.rollback();
          throw error;
        }
      });

      // Simulate failure during creation
      boardService._createBoardRecord = jest.fn().mockRejectedValue(new Error('DB error'));

      await expect(boardService.createBoard(boardData)).rejects.toThrow();

      
      expect(rolledBack).toBe(true);
    });
  });

  describe('Redis connection management', () => {
    
    it('should not leak redis connections', async () => {
      const boardService = new BoardService(mockSequelize, mockRedis);

      const connectionCount = { current: 0, max: 0 };

      mockRedis.duplicate.mockImplementation(() => {
        connectionCount.current++;
        connectionCount.max = Math.max(connectionCount.max, connectionCount.current);
        return {
          connect: jest.fn().mockResolvedValue(undefined),
          get: jest.fn().mockResolvedValue(null),
          set: jest.fn().mockResolvedValue('OK'),
          quit: jest.fn().mockImplementation(() => {
            connectionCount.current--;
            return Promise.resolve('OK');
          }),
        };
      });

      // Perform multiple operations
      for (let i = 0; i < 10; i++) {
        await boardService.getBoardWithCache(`board-${i}`);
      }

      
      expect(connectionCount.current).toBe(0);
      expect(connectionCount.max).toBeLessThanOrEqual(5); // Should pool connections
    });

    
    it('connection pool test', async () => {
      const boardService = new BoardService(mockSequelize, mockRedis);

      const activeConnections = new Set();

      mockRedis.duplicate.mockImplementation(() => {
        const connId = `conn-${Math.random()}`;
        activeConnections.add(connId);
        return {
          id: connId,
          connect: jest.fn().mockResolvedValue(undefined),
          get: jest.fn().mockResolvedValue(null),
          quit: jest.fn().mockImplementation(() => {
            activeConnections.delete(connId);
            return Promise.resolve('OK');
          }),
        };
      });

      // Concurrent operations
      await Promise.all(
        Array(20).fill(null).map((_, i) =>
          boardService.getBoardWithCache(`board-${i}`)
        )
      );

      // All connections should be returned to pool or closed
      expect(activeConnections.size).toBe(0);
    });
  });

  describe('N+1 query prevention', () => {
    
    it('should not have N+1 query', async () => {
      const boardService = new BoardService(mockSequelize, mockRedis);

      const queryCount = { count: 0 };

      boardService._findBoards = jest.fn().mockImplementation(async () => {
        queryCount.count++;
        return [
          { id: 'board-1', ownerId: 'user-1' },
          { id: 'board-2', ownerId: 'user-1' },
          { id: 'board-3', ownerId: 'user-2' },
        ];
      });

      boardService._findElements = jest.fn().mockImplementation(async () => {
        queryCount.count++;
        return [];
      });

      boardService._findMembers = jest.fn().mockImplementation(async () => {
        queryCount.count++;
        return [];
      });

      await boardService.getBoardsWithDetails('user-1');

      
      // Should be 3 queries max (boards, elements, members with IN clause)
      expect(queryCount.count).toBeLessThanOrEqual(3);
    });

    
    it('query count test', async () => {
      const boardService = new BoardService(mockSequelize, mockRedis);

      const queries = [];

      boardService._executeQuery = jest.fn().mockImplementation(async (sql) => {
        queries.push(sql);
        return [];
      });

      // Load 10 boards with their elements
      await boardService.loadBoardsWithElements(['b1', 'b2', 'b3', 'b4', 'b5', 'b6', 'b7', 'b8', 'b9', 'b10']);

      // Should use batch query, not individual queries
      expect(queries.length).toBeLessThanOrEqual(2);
    });
  });
});

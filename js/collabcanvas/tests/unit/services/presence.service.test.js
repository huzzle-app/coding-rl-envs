/**
 * Presence Service Unit Tests
 *
 * Tests bugs A3 (memory leak) and A5 (event loop blocking)
 */

const PresenceService = require('../../../src/services/collaboration/presence.service');

describe('PresenceService', () => {
  let presenceService;
  let mockSocket;
  let mockRedis;

  beforeEach(() => {
    mockRedis = {
      hset: jest.fn().mockResolvedValue(1),
      hget: jest.fn().mockResolvedValue(null),
      hdel: jest.fn().mockResolvedValue(1),
      hgetall: jest.fn().mockResolvedValue({}),
      expire: jest.fn().mockResolvedValue(1),
    };

    presenceService = new PresenceService(mockRedis);

    mockSocket = {
      id: 'socket-123',
      on: jest.fn(),
      off: jest.fn(),
      emit: jest.fn(),
      removeListener: jest.fn(),
    };
  });

  afterEach(() => {
    jest.clearAllMocks();
  });

  describe('trackUser', () => {
    it('should add user to presence map', async () => {
      const boardId = 'board-1';
      const user = { id: 'user-1', name: 'Test User' };

      await presenceService.trackUser(mockSocket, boardId, user);

      expect(mockRedis.hset).toHaveBeenCalledWith(
        `presence:${boardId}`,
        user.id,
        expect.any(String)
      );
    });

    it('should set up heartbeat listener', async () => {
      const boardId = 'board-1';
      const user = { id: 'user-1', name: 'Test User' };

      await presenceService.trackUser(mockSocket, boardId, user);

      expect(mockSocket.on).toHaveBeenCalledWith('heartbeat', expect.any(Function));
    });

    it('should handle multiple users on same board', async () => {
      const boardId = 'board-1';
      const user1 = { id: 'user-1', name: 'User 1' };
      const user2 = { id: 'user-2', name: 'User 2' };

      const socket1 = { id: 'socket-1', on: jest.fn(), off: jest.fn() };
      const socket2 = { id: 'socket-2', on: jest.fn(), off: jest.fn() };

      await presenceService.trackUser(socket1, boardId, user1);
      await presenceService.trackUser(socket2, boardId, user2);

      expect(mockRedis.hset).toHaveBeenCalledTimes(2);
    });
  });

  describe('removeUser', () => {
    it('should remove user from presence map', async () => {
      const boardId = 'board-1';
      const userId = 'user-1';

      await presenceService.removeUser(mockSocket, boardId, userId);

      expect(mockRedis.hdel).toHaveBeenCalledWith(`presence:${boardId}`, userId);
    });

    
    it('should not leak memory on user disconnect', async () => {
      const boardId = 'board-1';
      const user = { id: 'user-1', name: 'Test User' };

      // Track user (adds listener)
      await presenceService.trackUser(mockSocket, boardId, user);

      // Remove user (should remove listener)
      await presenceService.removeUser(mockSocket, boardId, user.id);

      
      expect(mockSocket.off).toHaveBeenCalledWith('heartbeat', expect.any(Function));
    });

    it('should handle removing non-existent user', async () => {
      const boardId = 'board-1';
      const userId = 'non-existent';

      await expect(
        presenceService.removeUser(mockSocket, boardId, userId)
      ).resolves.not.toThrow();
    });
  });

  describe('getActiveUsers', () => {
    it('should return all active users on board', async () => {
      const boardId = 'board-1';
      mockRedis.hgetall.mockResolvedValue({
        'user-1': JSON.stringify({ id: 'user-1', name: 'User 1', cursor: { x: 0, y: 0 } }),
        'user-2': JSON.stringify({ id: 'user-2', name: 'User 2', cursor: { x: 100, y: 100 } }),
      });

      const users = await presenceService.getActiveUsers(boardId);

      expect(users).toHaveLength(2);
      expect(users[0].id).toBe('user-1');
      expect(users[1].id).toBe('user-2');
    });

    it('should return empty array for empty board', async () => {
      const boardId = 'empty-board';
      mockRedis.hgetall.mockResolvedValue({});

      const users = await presenceService.getActiveUsers(boardId);

      expect(users).toEqual([]);
    });
  });

  describe('updateCursor', () => {
    it('should update cursor position', async () => {
      const boardId = 'board-1';
      const userId = 'user-1';
      const position = { x: 150, y: 200 };

      mockRedis.hget.mockResolvedValue(JSON.stringify({
        id: userId,
        name: 'User 1',
        cursor: { x: 0, y: 0 },
      }));

      await presenceService.updateCursor(boardId, userId, position);

      expect(mockRedis.hset).toHaveBeenCalled();
    });

    it('should handle cursor update for non-tracked user', async () => {
      const boardId = 'board-1';
      const userId = 'user-1';
      const position = { x: 150, y: 200 };

      mockRedis.hget.mockResolvedValue(null);

      // Should not throw
      await expect(
        presenceService.updateCursor(boardId, userId, position)
      ).resolves.not.toThrow();
    });
  });

  describe('memory leak detection', () => {
    
    it('test memory leak detection', async () => {
      const listeners = [];
      const leakSocket = {
        id: 'leak-socket',
        on: jest.fn((event, handler) => {
          listeners.push({ event, handler });
        }),
        off: jest.fn((event, handler) => {
          const idx = listeners.findIndex(l => l.event === event && l.handler === handler);
          if (idx !== -1) listeners.splice(idx, 1);
        }),
      };

      const boardId = 'board-1';
      const user = { id: 'user-1', name: 'User 1' };

      // Track multiple times (simulating reconnects)
      for (let i = 0; i < 5; i++) {
        await presenceService.trackUser(leakSocket, boardId, user);
        await presenceService.removeUser(leakSocket, boardId, user.id);
      }

      
      // After 5 track/remove cycles, there should be 0 listeners
      expect(listeners.length).toBe(0);
    });
  });

  describe('event loop blocking', () => {
    
    it('should not block event loop', async () => {
      const boardId = 'board-1';

      // Create large state
      const users = {};
      for (let i = 0; i < 1000; i++) {
        users[`user-${i}`] = JSON.stringify({
          id: `user-${i}`,
          name: `User ${i}`,
          cursor: { x: i, y: i },
          selection: Array(100).fill({ elementId: `elem-${i}` }),
        });
      }
      mockRedis.hgetall.mockResolvedValue(users);

      const startTime = Date.now();
      await presenceService.getActiveUsers(boardId);
      const duration = Date.now() - startTime;

      // Should complete in reasonable time (< 100ms)
      expect(duration).toBeLessThan(100);
    });

    
    it('performance test for large state', async () => {
      const boardId = 'board-1';

      // Generate large presence data
      const largeState = {};
      for (let i = 0; i < 500; i++) {
        largeState[`user-${i}`] = JSON.stringify({
          id: `user-${i}`,
          name: `User ${i}`,
          cursor: { x: Math.random() * 1000, y: Math.random() * 1000 },
          selection: Array(50).fill(null).map((_, j) => ({
            elementId: `element-${j}`,
            type: 'rectangle',
          })),
        });
      }

      mockRedis.hgetall.mockResolvedValue(largeState);

      // Measure time for serialization/deserialization
      const iterations = 10;
      const times = [];

      for (let i = 0; i < iterations; i++) {
        const start = process.hrtime.bigint();
        await presenceService.getActiveUsers(boardId);
        const end = process.hrtime.bigint();
        times.push(Number(end - start) / 1e6); // Convert to ms
      }

      const avgTime = times.reduce((a, b) => a + b, 0) / times.length;

      // Average time should be reasonable
      expect(avgTime).toBeLessThan(50);
    });
  });

  describe('heartbeat handling', () => {
    it('should update last seen on heartbeat', async () => {
      const boardId = 'board-1';
      const user = { id: 'user-1', name: 'User 1' };

      let heartbeatHandler;
      mockSocket.on.mockImplementation((event, handler) => {
        if (event === 'heartbeat') {
          heartbeatHandler = handler;
        }
      });

      await presenceService.trackUser(mockSocket, boardId, user);

      // Simulate heartbeat
      if (heartbeatHandler) {
        await heartbeatHandler();
      }

      // Should have updated presence
      expect(mockRedis.hset).toHaveBeenCalledTimes(2); // Initial + heartbeat
    });

    it('should expire presence after timeout', async () => {
      const boardId = 'board-1';
      const user = { id: 'user-1', name: 'User 1' };

      await presenceService.trackUser(mockSocket, boardId, user);

      expect(mockRedis.expire).toHaveBeenCalledWith(
        `presence:${boardId}`,
        expect.any(Number)
      );
    });
  });
});

/**
 * Broadcast Service Unit Tests
 */

const BroadcastService = require('../../../src/services/collaboration/broadcast.service');

describe('BroadcastService', () => {
  let broadcastService;
  let mockIo;
  let mockRedis;

  beforeEach(() => {
    mockIo = {
      to: jest.fn().mockReturnThis(),
      emit: jest.fn(),
    };

    mockRedis = {
      publish: jest.fn().mockResolvedValue(1),
      subscribe: jest.fn().mockResolvedValue('OK'),
      on: jest.fn(),
    };

    broadcastService = new BroadcastService(mockIo, mockRedis);
  });

  afterEach(() => {
    jest.clearAllMocks();
  });

  describe('broadcastToBoard', () => {
    it('should emit to socket.io room', async () => {
      const boardId = 'board-1';
      const event = 'element:update';
      const data = { elementId: 'elem-1', changes: { x: 100 } };

      await broadcastService.broadcastToBoard(boardId, event, data);

      expect(mockIo.to).toHaveBeenCalledWith(`board:${boardId}`);
      expect(mockIo.emit).toHaveBeenCalledWith(event, data);
    });

    
    it('should emit to socket.io room immediately', async () => {
      const boardId = 'board-1';
      const event = 'element:create';
      const data = { elementId: 'elem-new', type: 'rectangle' };

      const emitOrder = [];
      mockIo.emit.mockImplementation(() => {
        emitOrder.push('emit');
      });

      const result = await broadcastService.broadcastToBoard(boardId, event, data);
      emitOrder.push('return');

      // Emit should happen before return
      expect(emitOrder).toEqual(['emit', 'return']);
      expect(result).toBeDefined();
    });

    it('should handle empty data', async () => {
      const boardId = 'board-1';
      const event = 'ping';

      await broadcastService.broadcastToBoard(boardId, event, {});

      expect(mockIo.emit).toHaveBeenCalledWith(event, {});
    });
  });

  describe('broadcastToUser', () => {
    it('should emit to specific user socket', async () => {
      const userId = 'user-1';
      const event = 'notification';
      const data = { message: 'Hello' };

      await broadcastService.broadcastToUser(userId, event, data);

      expect(mockIo.to).toHaveBeenCalledWith(`user:${userId}`);
      expect(mockIo.emit).toHaveBeenCalledWith(event, data);
    });
  });

  describe('publishToPubSub', () => {
    it('should publish message to Redis channel', async () => {
      const channel = 'board-updates';
      const message = { boardId: 'board-1', operation: 'update' };

      await broadcastService.publishToPubSub(channel, message);

      expect(mockRedis.publish).toHaveBeenCalledWith(
        channel,
        JSON.stringify(message)
      );
    });

    it('should propagate publish errors to caller', async () => {
      const channel = 'board-updates';
      const message = { boardId: 'board-1' };

      // Track unhandled rejections to prevent test crash
      const unhandledRejections = [];
      const handler = (reason) => unhandledRejections.push(reason);
      process.on('unhandledRejection', handler);

      mockRedis.publish.mockRejectedValue(new Error('Connection lost'));

      // BUG A1: publishToPubSub doesn't await redis.publish, so the error
      // is lost as an unhandled rejection instead of propagating to the caller.
      // When fixed, this should reject with 'Connection lost'.
      const result = await broadcastService.publishToPubSub(channel, message);

      // Allow microtasks to flush so unhandled rejection fires
      await new Promise(r => setTimeout(r, 10));

      // The error should NOT be silently lost — it should propagate to the caller.
      // With the bug, result resolves to { success: true } and the error
      // fires as an unhandled rejection.
      expect(result).not.toEqual({ success: true });

      process.off('unhandledRejection', handler);
    });
  });

  describe('broadcastExcept', () => {
    it('should broadcast to all except sender', async () => {
      const boardId = 'board-1';
      const senderId = 'socket-1';
      const event = 'element:move';
      const data = { elementId: 'elem-1', position: { x: 50, y: 50 } };

      const mockSenderSocket = { id: senderId, broadcast: mockIo };

      await broadcastService.broadcastExcept(mockSenderSocket, boardId, event, data);

      expect(mockIo.to).toHaveBeenCalledWith(`board:${boardId}`);
      expect(mockIo.emit).toHaveBeenCalledWith(event, data);
    });
  });

  describe('batch broadcasting', () => {
    it('should handle multiple broadcasts efficiently', async () => {
      const boardId = 'board-1';
      const updates = Array(100).fill(null).map((_, i) => ({
        event: 'element:update',
        data: { elementId: `elem-${i}`, changes: { x: i * 10 } },
      }));

      const startTime = Date.now();

      await Promise.all(
        updates.map(u => broadcastService.broadcastToBoard(boardId, u.event, u.data))
      );

      const duration = Date.now() - startTime;

      expect(mockIo.emit).toHaveBeenCalledTimes(100);
      expect(duration).toBeLessThan(100); // Should be fast
    });
  });
});

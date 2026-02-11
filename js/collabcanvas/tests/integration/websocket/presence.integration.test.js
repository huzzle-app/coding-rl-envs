/**
 * Presence WebSocket Integration Tests
 *
 * Tests bugs A3 (memory leak), A4 (stale closure), A5 (event loop blocking)
 */

describe('Presence WebSocket Integration', () => {
  let mockIo;
  let mockSocket;
  let presenceHandler;

  beforeEach(() => {
    mockSocket = {
      id: 'socket-123',
      userId: 'user-1',
      on: jest.fn(),
      off: jest.fn(),
      emit: jest.fn(),
      join: jest.fn(),
      leave: jest.fn(),
      removeListener: jest.fn(),
      removeAllListeners: jest.fn(),
    };

    mockIo = {
      to: jest.fn().mockReturnThis(),
      emit: jest.fn(),
    };

    presenceHandler = require('../../../src/websocket/handlers/presence.handler');
  });

  afterEach(() => {
    jest.clearAllMocks();
  });

  describe('board switching', () => {
    
    it('should use current board after board switch', async () => {
      const boards = [];
      const handler = presenceHandler(mockSocket, mockIo);

      // Track which board cursor updates go to
      handler.onCursorUpdate = jest.fn().mockImplementation((boardId, position) => {
        boards.push(boardId);
      });

      // Join first board
      await handler.joinBoard('board-1');

      // Move cursor
      await handler.cursorMove({ x: 100, y: 100 });

      // Switch to second board
      await handler.joinBoard('board-2');

      // Move cursor again
      await handler.cursorMove({ x: 200, y: 200 });

      
      expect(boards).toEqual(['board-1', 'board-2']);
    });

    
    it('stale closure test', async () => {
      const handler = presenceHandler(mockSocket, mockIo);

      let capturedBoard = null;

      // Join board and capture the closure
      await handler.joinBoard('board-A');

      const cursorHandler = mockSocket.on.mock.calls.find(
        call => call[0] === 'cursor-move'
      )?.[1];

      // Switch board
      await handler.joinBoard('board-B');

      // The cursor handler should use updated board reference
      if (cursorHandler) {
        await cursorHandler({ x: 50, y: 50 });
      }

      // Should emit to board-B, not board-A
      const emitCalls = mockIo.to.mock.calls;
      const lastCall = emitCalls[emitCalls.length - 1];

      expect(lastCall[0]).toBe('board:board-B');
    });
  });

  describe('memory management', () => {
    
    it('should clean up listeners on disconnect', async () => {
      const handler = presenceHandler(mockSocket, mockIo);

      // Join board (adds listeners)
      await handler.joinBoard('board-1');

      // Count listeners added
      const listenersAdded = mockSocket.on.mock.calls.length;

      // Disconnect
      await handler.disconnect();

      // Should remove all listeners that were added
      const listenersRemoved = mockSocket.off.mock.calls.length +
        mockSocket.removeListener.mock.calls.length;

      expect(listenersRemoved).toBeGreaterThanOrEqual(listenersAdded - 1); // -1 for disconnect itself
    });

    
    it('should not accumulate listeners on reconnect', async () => {
      const handler = presenceHandler(mockSocket, mockIo);

      // Simulate multiple reconnects
      for (let i = 0; i < 5; i++) {
        await handler.joinBoard('board-1');
        await handler.leaveBoard('board-1');
      }

      // Count unique listener types
      const listenerTypes = new Set(
        mockSocket.on.mock.calls.map(call => call[0])
      );

      // Should not have duplicate listeners for same event
      const cursorListeners = mockSocket.on.mock.calls.filter(
        call => call[0] === 'cursor-move'
      );

      
      expect(cursorListeners.length).toBeLessThanOrEqual(1);
    });
  });

  describe('event loop performance', () => {
    
    it('should not block event loop with large presence data', async () => {
      const handler = presenceHandler(mockSocket, mockIo);

      // Create large presence state
      const largePresence = {};
      for (let i = 0; i < 1000; i++) {
        largePresence[`user-${i}`] = {
          id: `user-${i}`,
          name: `User ${i}`,
          cursor: { x: Math.random() * 1000, y: Math.random() * 1000 },
          selection: Array(50).fill(null).map((_, j) => `element-${j}`),
        };
      }

      handler._getPresenceState = jest.fn().mockResolvedValue(largePresence);

      const startTime = Date.now();

      // This should not block
      await handler.getPresence('board-1');

      const duration = Date.now() - startTime;

      expect(duration).toBeLessThan(100);
    });

    
    it('should handle rapid cursor updates without blocking', async () => {
      const handler = presenceHandler(mockSocket, mockIo);

      await handler.joinBoard('board-1');

      const startTime = Date.now();

      // Rapid updates
      const updates = [];
      for (let i = 0; i < 100; i++) {
        updates.push(handler.cursorMove({ x: i, y: i }));
      }

      await Promise.all(updates);

      const duration = Date.now() - startTime;

      // Should complete quickly even with many updates
      expect(duration).toBeLessThan(500);
    });
  });

  describe('concurrent operations', () => {
    it('should handle multiple users joining same board', async () => {
      const sockets = Array(10).fill(null).map((_, i) => ({
        id: `socket-${i}`,
        userId: `user-${i}`,
        on: jest.fn(),
        off: jest.fn(),
        emit: jest.fn(),
        join: jest.fn(),
        leave: jest.fn(),
      }));

      const handlers = sockets.map(s => presenceHandler(s, mockIo));

      // All join same board
      await Promise.all(handlers.map(h => h.joinBoard('board-shared')));

      // All should have joined
      sockets.forEach(s => {
        expect(s.join).toHaveBeenCalledWith('board:board-shared');
      });
    });

    it('should broadcast presence to all users', async () => {
      const handler = presenceHandler(mockSocket, mockIo);

      await handler.joinBoard('board-1');
      await handler.cursorMove({ x: 100, y: 100 });

      expect(mockIo.to).toHaveBeenCalledWith('board:board-1');
      expect(mockIo.emit).toHaveBeenCalled();
    });
  });
});

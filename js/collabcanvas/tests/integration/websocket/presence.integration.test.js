/**
 * Presence WebSocket Integration Tests
 *
 * Tests bugs A3 (memory leak), A4 (stale closure), A5 (event loop blocking)
 */

const setupPresenceHandlers = require('../../../src/websocket/handlers/presence.handler');

describe('Presence WebSocket Integration', () => {
  let mockIo;
  let mockSocket;
  let mockPresenceService;
  let mockBroadcastService;

  beforeEach(() => {
    mockSocket = {
      id: 'socket-123',
      userId: 'user-1',
      user: { id: 'user-1', firstName: 'Test', lastName: 'User', avatarUrl: null },
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

    mockPresenceService = {
      trackUser: jest.fn().mockResolvedValue([]),
      removeUser: jest.fn().mockResolvedValue([]),
      updateCursor: jest.fn().mockResolvedValue({}),
      updateSelection: jest.fn().mockResolvedValue({}),
      getBoardPresence: jest.fn().mockResolvedValue([]),
    };

    mockBroadcastService = {
      broadcastPresence: jest.fn().mockResolvedValue({ success: true }),
      broadcastCursor: jest.fn().mockResolvedValue({ success: true }),
      broadcastSelection: jest.fn().mockResolvedValue({ success: true }),
    };
  });

  afterEach(() => {
    jest.clearAllMocks();
  });

  function getHandler(eventName) {
    const call = mockSocket.on.mock.calls.find(c => c[0] === eventName);
    return call ? call[1] : null;
  }

  describe('board switching', () => {
    /**
     * BUG A4: Stale closure captures old board reference.
     * When user switches boards, cursor-move handlers registered inside
     * join-board still reference the old board via closure.
     */
    it('should use current board after board switch', async () => {
      setupPresenceHandlers(mockIo, mockSocket, {
        presenceService: mockPresenceService,
        broadcastService: mockBroadcastService,
      });

      const joinBoardHandler = getHandler('join-board');
      expect(joinBoardHandler).toBeDefined();

      // Join first board
      const cb1 = jest.fn();
      await joinBoardHandler('board-1', cb1);

      // Get cursor-move handler registered during join
      const cursorMoveHandler = getHandler('cursor-move');
      expect(cursorMoveHandler).toBeDefined();

      // Move cursor on first board
      await cursorMoveHandler({ x: 100, y: 100 });

      expect(mockBroadcastService.broadcastCursor).toHaveBeenCalledWith(
        'board-1', 'user-1', { x: 100, y: 100 }, 'socket-123'
      );

      // Switch to second board
      const cb2 = jest.fn();
      await joinBoardHandler('board-2', cb2);

      // Move cursor again — should go to board-2, not board-1
      mockBroadcastService.broadcastCursor.mockClear();
      await cursorMoveHandler({ x: 200, y: 200 });

      // BUG A4: The cursor-move handler uses a stale closure referencing the
      // old board variable. After switching boards, updates should target board-2,
      // but the closure may still capture 'board-1'.
      expect(mockBroadcastService.broadcastCursor).toHaveBeenCalledWith(
        'board-2', 'user-1', { x: 200, y: 200 }, 'socket-123'
      );
    });

    /**
     * BUG A4: Stale closure captures old board for selection-change too
     */
    it('should update selection on current board after switch', async () => {
      setupPresenceHandlers(mockIo, mockSocket, {
        presenceService: mockPresenceService,
        broadcastService: mockBroadcastService,
      });

      const joinBoardHandler = getHandler('join-board');

      // Join board-A
      await joinBoardHandler('board-A', jest.fn());

      const selectionHandler = getHandler('selection-change');
      expect(selectionHandler).toBeDefined();

      // Switch to board-B
      await joinBoardHandler('board-B', jest.fn());

      // Selection change should target board-B
      await selectionHandler(['elem-1', 'elem-2']);

      expect(mockPresenceService.updateSelection).toHaveBeenCalledWith(
        'board-B', 'user-1', ['elem-1', 'elem-2']
      );
    });
  });

  describe('memory management', () => {
    /**
     * BUG A4: Each call to join-board registers NEW cursor-move and
     * selection-change listeners without removing old ones, causing
     * listener accumulation.
     */
    it('should not accumulate listeners on board switch', async () => {
      setupPresenceHandlers(mockIo, mockSocket, {
        presenceService: mockPresenceService,
        broadcastService: mockBroadcastService,
      });

      const joinBoardHandler = getHandler('join-board');

      // Switch boards 5 times
      for (let i = 0; i < 5; i++) {
        await joinBoardHandler(`board-${i}`, jest.fn());
      }

      // Count how many cursor-move handlers were registered
      const cursorListeners = mockSocket.on.mock.calls.filter(
        call => call[0] === 'cursor-move'
      );

      // BUG A4: Without cleanup, each join-board adds a new cursor-move listener.
      // After 5 switches, there should be at most 1 cursor-move listener,
      // not 5. The handler should remove old listeners before adding new ones.
      expect(cursorListeners.length).toBeLessThanOrEqual(1);
    });

    /**
     * BUG A3: Heartbeat listener not removed on disconnect
     */
    it('should clean up heartbeat listener on disconnect', async () => {
      setupPresenceHandlers(mockIo, mockSocket, {
        presenceService: mockPresenceService,
        broadcastService: mockBroadcastService,
      });

      const joinBoardHandler = getHandler('join-board');
      await joinBoardHandler('board-1', jest.fn());

      // Count listeners added during join
      const listenersAdded = mockSocket.on.mock.calls.length;

      // Trigger disconnect
      const disconnectHandler = getHandler('disconnect');
      expect(disconnectHandler).toBeDefined();
      await disconnectHandler();

      // Should have removed event listeners on disconnect
      const listenersRemoved = mockSocket.off.mock.calls.length +
        mockSocket.removeListener.mock.calls.length;

      expect(listenersRemoved).toBeGreaterThanOrEqual(listenersAdded - 1);
    });
  });

  describe('concurrent operations', () => {
    it('should handle multiple users joining same board', async () => {
      const sockets = Array(5).fill(null).map((_, i) => ({
        id: `socket-${i}`,
        userId: `user-${i}`,
        user: { id: `user-${i}`, firstName: `User`, lastName: `${i}`, avatarUrl: null },
        on: jest.fn(),
        off: jest.fn(),
        emit: jest.fn(),
        join: jest.fn(),
        leave: jest.fn(),
      }));

      sockets.forEach(s => {
        setupPresenceHandlers(mockIo, s, {
          presenceService: mockPresenceService,
          broadcastService: mockBroadcastService,
        });
      });

      // All join same board
      for (const s of sockets) {
        const joinHandler = s.on.mock.calls.find(c => c[0] === 'join-board')?.[1];
        if (joinHandler) {
          await joinHandler('board-shared', jest.fn());
        }
      }

      // All should have joined the room
      sockets.forEach(s => {
        expect(s.join).toHaveBeenCalledWith('board:board-shared');
      });
    });

    it('should broadcast presence update on join', async () => {
      setupPresenceHandlers(mockIo, mockSocket, {
        presenceService: mockPresenceService,
        broadcastService: mockBroadcastService,
      });

      const joinBoardHandler = getHandler('join-board');
      await joinBoardHandler('board-1', jest.fn());

      expect(mockBroadcastService.broadcastPresence).toHaveBeenCalledWith(
        'board-1', 'join', mockSocket.user, 'socket-123'
      );
    });
  });

  describe('leave and disconnect', () => {
    it('should leave board and broadcast leave event', async () => {
      setupPresenceHandlers(mockIo, mockSocket, {
        presenceService: mockPresenceService,
        broadcastService: mockBroadcastService,
      });

      const joinBoardHandler = getHandler('join-board');
      await joinBoardHandler('board-1', jest.fn());

      const leaveBoardHandler = getHandler('leave-board');
      expect(leaveBoardHandler).toBeDefined();

      const cb = jest.fn();
      await leaveBoardHandler('board-1', cb);

      expect(mockSocket.leave).toHaveBeenCalledWith('board:board-1');
      expect(mockPresenceService.removeUser).toHaveBeenCalledWith(
        mockSocket, 'board-1', 'user-1'
      );
      expect(cb).toHaveBeenCalledWith({ success: true });
    });

    it('should clean up on disconnect', async () => {
      setupPresenceHandlers(mockIo, mockSocket, {
        presenceService: mockPresenceService,
        broadcastService: mockBroadcastService,
      });

      const joinBoardHandler = getHandler('join-board');
      await joinBoardHandler('board-1', jest.fn());

      const disconnectHandler = getHandler('disconnect');
      await disconnectHandler();

      expect(mockPresenceService.removeUser).toHaveBeenCalledWith(
        mockSocket, 'board-1', 'user-1'
      );
      expect(mockBroadcastService.broadcastPresence).toHaveBeenCalledWith(
        'board-1', 'leave', mockSocket.user, 'socket-123'
      );
    });
  });
});

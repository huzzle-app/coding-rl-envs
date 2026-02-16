/**
 * WebSocket System Tests
 *
 * End-to-end WebSocket functionality tests using actual SyncService and PresenceService.
 * Tests bugs A1 (missing await), A2 (race condition), A3 (memory leak)
 */

const SyncService = require('../../src/services/canvas/sync.service');
const PresenceService = require('../../src/services/collaboration/presence.service');
const BroadcastService = require('../../src/services/collaboration/broadcast.service');

describe('WebSocket System', () => {
  let syncService;
  let presenceService;
  let broadcastService;
  let mockIo;
  let mockRedis;

  beforeEach(() => {
    mockIo = {
      to: jest.fn().mockReturnThis(),
      except: jest.fn().mockReturnThis(),
      emit: jest.fn(),
    };

    mockRedis = {
      get: jest.fn().mockResolvedValue(null),
      set: jest.fn().mockResolvedValue('OK'),
      del: jest.fn().mockResolvedValue(1),
      hset: jest.fn().mockResolvedValue(1),
      hget: jest.fn().mockResolvedValue(null),
      hdel: jest.fn().mockResolvedValue(1),
      hgetall: jest.fn().mockResolvedValue({}),
      expire: jest.fn().mockResolvedValue(1),
      publish: jest.fn().mockResolvedValue(1),
      subscribe: jest.fn().mockResolvedValue(),
      on: jest.fn(),
    };

    // Create sync service with proper constructor
    syncService = new SyncService(mockIo, {});
    syncService.redis = mockRedis;
    syncService.pubClient = mockRedis;
    syncService.subClient = mockRedis;

    presenceService = new PresenceService(mockRedis);
    broadcastService = new BroadcastService(mockIo, mockRedis);
  });

  afterEach(() => {
    jest.clearAllMocks();
  });

  describe('real-time synchronization', () => {
    it('should sync state changes via SyncService', async () => {
      mockRedis.get.mockResolvedValue(JSON.stringify({
        elements: { 'elem-1': { x: 0, y: 0 } },
        version: 1,
      }));

      const mockCrdt = {
        applyOperation: jest.fn((op, state) => ({
          ...state,
          elements: {
            ...state.elements,
            [op.elementId]: { ...state.elements?.[op.elementId], ...op.changes },
          },
        })),
      };
      syncService.crdt = mockCrdt;

      const result = await syncService.applyUpdate('board-1', {
        type: 'update',
        elementId: 'elem-1',
        changes: { x: 100 },
      });

      expect(result.success).toBe(true);
      expect(mockRedis.set).toHaveBeenCalled();
    });

    /**
     * BUG A1: broadcastUpdate doesn't await Redis publish.
     */
    it('should complete broadcast before returning', async () => {
      let publishResolved = false;
      mockRedis.publish.mockImplementation(() => {
        return new Promise(resolve => {
          setTimeout(() => {
            publishResolved = true;
            resolve(1);
          }, 10);
        });
      });

      await syncService.broadcastUpdate('board-1', {
        type: 'update',
        elementId: 'elem-1',
        changes: { x: 100 },
      });

      // BUG A1: publish is not awaited, so it may not resolve before return
      expect(publishResolved).toBe(true);
    });

    it('should broadcast to correct room', async () => {
      await syncService.broadcastUpdate('board-1', {
        type: 'create',
        elementId: 'elem-new',
      });

      expect(mockIo.to).toHaveBeenCalledWith('board:board-1');
      expect(mockIo.emit).toHaveBeenCalledWith('element-update', expect.any(Object));
    });
  });

  describe('presence system', () => {
    it('should track and retrieve active users', async () => {
      const mockSocket = { id: 'socket-1', on: jest.fn(), off: jest.fn() };
      const user = { id: 'user-1', firstName: 'Test', lastName: 'User' };

      await presenceService.trackUser(mockSocket, 'board-1', user);

      const presence = await presenceService.getBoardPresence('board-1');
      expect(presence).toHaveLength(1);
    });

    it('should remove user from presence on disconnect', async () => {
      const mockSocket = { id: 'socket-1', on: jest.fn(), off: jest.fn() };
      const user = { id: 'user-1', firstName: 'Test', lastName: 'User' };

      await presenceService.trackUser(mockSocket, 'board-1', user);
      await presenceService.removeUser(mockSocket, 'board-1', 'user-1');

      const presence = await presenceService.getBoardPresence('board-1');
      expect(presence).toHaveLength(0);
    });

    it('should handle multiple users on same board', async () => {
      for (let i = 0; i < 5; i++) {
        const socket = { id: `socket-${i}`, on: jest.fn(), off: jest.fn() };
        const user = { id: `user-${i}`, firstName: `User`, lastName: `${i}` };
        await presenceService.trackUser(socket, 'board-1', user);
      }

      expect(presenceService.getUserCount('board-1')).toBe(5);
    });
  });

  describe('broadcast service', () => {
    it('should broadcast to board room', async () => {
      await broadcastService.broadcastToBoard('board-1', 'element:update', {
        elementId: 'elem-1',
        changes: { x: 100 },
      });

      expect(mockIo.to).toHaveBeenCalledWith('board:board-1');
      expect(mockIo.emit).toHaveBeenCalled();
    });

    it('should broadcast to specific user', async () => {
      await broadcastService.broadcastToUser('user-1', 'notification', {
        message: 'Hello',
      });

      expect(mockIo.to).toHaveBeenCalledWith('user:user-1');
      expect(mockIo.emit).toHaveBeenCalledWith('notification', expect.any(Object));
    });

    it('should broadcast cursor via service', async () => {
      await broadcastService.broadcastCursor('board-1', 'user-1', { x: 100, y: 200 }, 'socket-1');

      // Should delegate to broadcastToBoard
      expect(mockIo.to).toHaveBeenCalled();
    });
  });

  describe('error recovery', () => {
    it('should handle getBoardState for non-existent board', async () => {
      mockRedis.get.mockResolvedValue(null);

      const state = await syncService.getBoardState('non-existent');

      expect(state).toBeDefined();
      expect(state.elements).toBeDefined();
    });

    it('should handle setState correctly', async () => {
      const state = { elements: { 'elem-1': { x: 100 } }, version: 1 };

      await syncService.setState('board-1', state);

      expect(mockRedis.set).toHaveBeenCalledWith(
        'board:board-1:state',
        JSON.stringify(state)
      );
    });
  });

  describe('event loop blocking (BUG A5)', () => {
    let setupConnectionHandlers;

    beforeEach(() => {
      setupConnectionHandlers = require('../../src/websocket/handlers/connection.handler');
    });

    /**
     * BUG A5: get-canvas-state does a redundant JSON.stringify + JSON.parse
     * round-trip that blocks the event loop for large state objects.
     * The handler should return the state directly without serialization.
     */
    it('should not perform redundant JSON round-trip on state retrieval', async () => {
      const mockSocket = {
        id: 'socket-1',
        on: jest.fn(),
        userId: 'user-1',
        user: { id: 'user-1' },
        connectedAt: Date.now(),
      };

      const stateElements = {};
      for (let i = 0; i < 100; i++) {
        stateElements[`elem-${i}`] = {
          x: i, y: i, width: 100, height: 100,
          content: { text: `Element ${i}` },
        };
      }

      const mockSyncService = {
        getFullState: jest.fn().mockResolvedValue({
          elements: stateElements,
          version: 42,
        }),
      };
      const mockHistoryService = {
        getHistoryInfo: jest.fn().mockReturnValue({ canUndo: false, canRedo: false }),
      };

      setupConnectionHandlers(mockIo, mockSocket, {
        syncService: mockSyncService,
        historyService: mockHistoryService,
      });

      // Find the 'get-canvas-state' handler
      const getStateCall = mockSocket.on.mock.calls.find(
        ([event]) => event === 'get-canvas-state'
      );
      expect(getStateCall).toBeDefined();
      const handler = getStateCall[1];

      // Track JSON.stringify calls using spyOn
      const stringifySpy = jest.spyOn(JSON, 'stringify');

      const result = await new Promise((resolve) => {
        handler('board-1', resolve);
      });

      // BUG A5: The handler does JSON.stringify(state) then JSON.parse(serializedState)
      // This redundant round-trip blocks the event loop for large objects.
      // A fixed handler should return the state directly without serialization.
      expect(result.success).toBe(true);
      expect(result.state).toBeDefined();
      expect(stringifySpy).not.toHaveBeenCalled();

      stringifySpy.mockRestore();
    });

    /**
     * BUG A5: sync-state handler also does blocking JSON operations
     */
    it('should not block event loop during state sync', async () => {
      const mockSocket = {
        id: 'socket-2',
        on: jest.fn(),
        userId: 'user-1',
      };

      const mockSyncService = {
        getFullState: jest.fn().mockResolvedValue({
          elements: { 'elem-1': { x: 0 } },
          version: 10,
        }),
      };
      const mockHistoryService = {
        getHistoryInfo: jest.fn().mockReturnValue({ canUndo: false, canRedo: false }),
      };

      setupConnectionHandlers(mockIo, mockSocket, {
        syncService: mockSyncService,
        historyService: mockHistoryService,
      });

      const syncStateCall = mockSocket.on.mock.calls.find(
        ([event]) => event === 'sync-state'
      );
      expect(syncStateCall).toBeDefined();
      const handler = syncStateCall[1];

      const stringifySpy = jest.spyOn(JSON, 'stringify');

      const result = await new Promise((resolve) => {
        handler('board-1', 5, resolve);
      });

      // BUG A5: sync-state also calls JSON.stringify on the state,
      // blocking the event loop for large payloads
      expect(result.success).toBe(true);
      expect(result.needsSync).toBe(true);
      expect(stringifySpy).not.toHaveBeenCalled();

      stringifySpy.mockRestore();
    });
  });
});

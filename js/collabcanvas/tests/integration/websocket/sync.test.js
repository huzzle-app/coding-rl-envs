/**
 * WebSocket Sync Integration Tests
 *
 * Tests for bugs A1 (missing await), A2 (race condition)
 */

const { createServer } = require('http');
const { Server } = require('socket.io');
const { io: ioc } = require('socket.io-client');
const SyncService = require('../../../src/services/canvas/sync.service');

describe('WebSocket Sync Integration Tests', () => {
  let io, httpServer, syncService;
  let clientSockets = [];
  const port = 3099;

  // Mock Redis for tests
  const mockRedis = {
    get: jest.fn().mockResolvedValue(null),
    set: jest.fn().mockResolvedValue('OK'),
    publish: jest.fn().mockResolvedValue(1),
    subscribe: jest.fn().mockResolvedValue(),
    on: jest.fn(),
    quit: jest.fn().mockResolvedValue(),
  };

  beforeAll((done) => {
    httpServer = createServer();
    io = new Server(httpServer, {
      cors: { origin: '*' },
    });

    httpServer.listen(port, () => {
      syncService = new SyncService(io, {});
      // Override Redis with mock
      syncService.redis = mockRedis;
      syncService.pubClient = mockRedis;
      syncService.subClient = mockRedis;

      done();
    });
  });

  afterAll(async () => {
    // Close all client sockets
    for (const socket of clientSockets) {
      socket.disconnect();
    }
    clientSockets = [];

    await new Promise((resolve) => {
      io.close(() => {
        httpServer.close(resolve);
      });
    });
  });

  afterEach(() => {
    // Disconnect any connected clients
    for (const socket of clientSockets) {
      socket.disconnect();
    }
    clientSockets = [];
    jest.clearAllMocks();
  });

  function createClient() {
    const socket = ioc(`http://localhost:${port}`, {
      transports: ['websocket'],
      autoConnect: false,
    });
    clientSockets.push(socket);
    return socket;
  }

  describe('Broadcast Operations (Bug A1)', () => {
    
    test('should complete broadcast before returning', async () => {
      const boardId = 'test-board-1';
      const operation = {
        id: 'op-1',
        elementId: 'elem-1',
        type: 'create',
        changes: { x: 100, y: 100 },
      };

      // Track when publish is called
      let publishCalled = false;
      mockRedis.publish.mockImplementation(() => {
        publishCalled = true;
        return Promise.resolve(1);
      });

      const result = await syncService.broadcastUpdate(boardId, operation);

      
      expect(result.success).toBe(true);

      // Give time for any async operations
      await new Promise(resolve => setTimeout(resolve, 50));

      // Publish should have been called
      expect(publishCalled).toBe(true);
      expect(mockRedis.publish).toHaveBeenCalled();
    });

    test('should emit to socket.io room immediately', (done) => {
      const client = createClient();
      const boardId = 'test-board-2';

      io.on('connection', (socket) => {
        socket.join(`board:${boardId}`);
      });

      client.on('connect', async () => {
        // Wait for room join
        await new Promise(resolve => setTimeout(resolve, 100));

        // Listen for the event
        client.on('element-update', (data) => {
          expect(data.elementId).toBe('elem-2');
          done();
        });

        // Broadcast
        await syncService.broadcastUpdate(boardId, {
          elementId: 'elem-2',
          type: 'update',
          changes: { x: 200 },
        });
      });

      client.connect();
    });
  });

  describe('State Synchronization (Bug A2)', () => {
    
    test('should maintain order of concurrent updates', async () => {
      const boardId = 'test-board-3';

      // Initialize board state
      await syncService.getBoardState(boardId);

      // Simulate concurrent updates
      const updates = [];
      for (let i = 0; i < 10; i++) {
        updates.push(
          syncService.applyUpdate(boardId, {
            elementId: `elem-${i}`,
            type: 'create',
            changes: { sequence: i, x: i * 10 },
          })
        );
      }

      await Promise.all(updates);

      // Check final state
      const state = await syncService.getFullState(boardId);

      
      expect(Object.keys(state.elements).length).toBe(10);

      // Verify all elements exist
      for (let i = 0; i < 10; i++) {
        expect(state.elements[`elem-${i}`]).toBeDefined();
        expect(state.elements[`elem-${i}`].sequence).toBe(i);
      }
    });

    test('should handle concurrent updates to same element', async () => {
      const boardId = 'test-board-4';
      const elementId = 'shared-element';

      // Create initial element
      await syncService.applyUpdate(boardId, {
        elementId,
        type: 'create',
        changes: { x: 0, y: 0, counter: 0 },
      });

      // Concurrent increments
      const increments = [];
      for (let i = 0; i < 10; i++) {
        increments.push(
          syncService.applyUpdate(boardId, {
            elementId,
            type: 'update',
            changes: { counter: i + 1 },
          })
        );
      }

      await Promise.all(increments);

      const state = await syncService.getFullState(boardId);

      
      // With correct locking/serialization, all 10 increments apply in order
      // and the last one (counter: 10) should be the final value.
      expect(state.elements[elementId]).toBeDefined();
      expect(state.elements[elementId].counter).toBe(10);
    });

    test('should increment version on each update', async () => {
      const boardId = 'test-board-5';

      const state1 = await syncService.applyUpdate(boardId, {
        elementId: 'elem-1',
        type: 'create',
        changes: { x: 0 },
      });

      const state2 = await syncService.applyUpdate(boardId, {
        elementId: 'elem-1',
        type: 'update',
        changes: { x: 100 },
      });

      expect(state2.version).toBeGreaterThan(state1.version);
    });
  });

  describe('Element Operations', () => {
    test('should create element', async () => {
      const boardId = 'test-board-6';
      const userId = 'user-1';

      const result = await syncService.createElement(
        boardId,
        { id: 'new-elem', type: 'rectangle', x: 50, y: 50 },
        userId
      );

      expect(result.operation.type).toBe('create');
      expect(result.state.elements['new-elem']).toBeDefined();
      expect(result.state.elements['new-elem'].createdBy).toBe(userId);
    });

    test('should update element', async () => {
      const boardId = 'test-board-7';
      const userId = 'user-1';

      // Create first
      await syncService.createElement(
        boardId,
        { id: 'elem-to-update', type: 'rectangle', x: 0, y: 0 },
        userId
      );

      // Update
      const result = await syncService.updateElement(
        boardId,
        'elem-to-update',
        { x: 100, y: 200 },
        userId,
        'socket-1'
      );

      expect(result.operation.type).toBe('update');
      expect(result.state.elements['elem-to-update'].x).toBe(100);
      expect(result.state.elements['elem-to-update'].y).toBe(200);
    });

    test('should delete element', async () => {
      const boardId = 'test-board-8';
      const userId = 'user-1';

      // Create first
      await syncService.createElement(
        boardId,
        { id: 'elem-to-delete', type: 'rectangle', x: 0, y: 0 },
        userId
      );

      // Delete
      const result = await syncService.deleteElement(
        boardId,
        'elem-to-delete',
        userId,
        'socket-1'
      );

      expect(result.operation.type).toBe('delete');
      expect(result.state.elements['elem-to-delete']).toBeUndefined();
    });
  });

  describe('Board State Management', () => {
    test('should initialize empty state for new board', async () => {
      const boardId = 'new-board-1';

      const state = await syncService.getBoardState(boardId);

      expect(state.version).toBe(1);
      expect(state.elements).toEqual({});
    });

    test('should cache state in memory', async () => {
      const boardId = 'cached-board-1';

      const state1 = await syncService.getBoardState(boardId);
      state1.custom = 'value';

      const state2 = await syncService.getBoardState(boardId);

      // Should return same object from cache
      expect(state2.custom).toBe('value');
    });

    test('should unload board from memory', async () => {
      const boardId = 'unload-board-1';

      await syncService.getBoardState(boardId);
      expect(syncService.boardStates.has(boardId)).toBe(true);

      await syncService.unloadBoard(boardId);
      expect(syncService.boardStates.has(boardId)).toBe(false);
    });
  });
});

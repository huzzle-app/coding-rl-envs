/**
 * Sync Service Unit Tests
 *
 * Tests bugs A1 (missing await) and A2 (race condition)
 */

const SyncService = require('../../../src/services/canvas/sync.service');

describe('SyncService', () => {
  let syncService;
  let mockRedis;
  let mockCrdt;
  let mockIo;

  beforeEach(() => {
    mockRedis = {
      get: jest.fn(),
      set: jest.fn().mockResolvedValue('OK'),
      publish: jest.fn().mockResolvedValue(1),
      setex: jest.fn().mockResolvedValue('OK'),
      watch: jest.fn().mockResolvedValue('OK'),
      multi: jest.fn().mockReturnValue({
        set: jest.fn().mockReturnThis(),
        exec: jest.fn().mockResolvedValue(['OK']),
      }),
      unwatch: jest.fn().mockResolvedValue('OK'),
    };

    mockCrdt = {
      applyOperation: jest.fn((op, state) => ({
        ...state,
        elements: {
          ...state.elements,
          [op.elementId]: { ...state.elements?.[op.elementId], ...op.changes },
        },
      })),
      generateOperationId: jest.fn(() => `op-${Date.now()}`),
    };

    mockIo = {
      to: jest.fn().mockReturnThis(),
      except: jest.fn().mockReturnThis(),
      emit: jest.fn(),
    };

    syncService = new SyncService(mockIo, {});
    // Inject mocks for testing
    syncService.redis = mockRedis;
    syncService.pubClient = mockRedis;
    syncService.subClient = mockRedis;
    syncService.crdt = mockCrdt;
  });

  afterEach(() => {
    jest.clearAllMocks();
  });

  describe('broadcastUpdate', () => {
    
    it('should complete broadcast before returning', async () => {
      const boardId = 'board-1';
      const operation = {
        type: 'update',
        elementId: 'elem-1',
        changes: { x: 100, y: 200 },
      };

      let publishResolved = false;
      mockRedis.publish.mockImplementation(() => {
        return new Promise(resolve => {
          setTimeout(() => {
            publishResolved = true;
            resolve(1);
          }, 10);
        });
      });

      await syncService.broadcastUpdate(boardId, operation);

      
      expect(publishResolved).toBe(true);
    });

    it('should include operation metadata', async () => {
      const boardId = 'board-1';
      const operation = {
        type: 'create',
        elementId: 'elem-new',
        data: { type: 'rectangle', x: 0, y: 0 },
      };

      await syncService.broadcastUpdate(boardId, operation);

      expect(mockRedis.publish).toHaveBeenCalledWith(
        'board-updates',
        expect.stringContaining(boardId)
      );
    });
  });

  describe('applyUpdate', () => {
    beforeEach(() => {
      mockRedis.get.mockResolvedValue(JSON.stringify({
        elements: { 'elem-1': { x: 0, y: 0 } },
        version: 1,
      }));
    });

    it('should apply operation to current state', async () => {
      const boardId = 'board-1';
      const operation = {
        type: 'update',
        elementId: 'elem-1',
        changes: { x: 100 },
      };

      const result = await syncService.applyUpdate(boardId, operation);

      expect(mockCrdt.applyOperation).toHaveBeenCalledWith(
        operation,
        expect.objectContaining({ elements: expect.any(Object) })
      );
      expect(result.success).toBe(true);
    });

    
    it('should handle concurrent updates to same element', async () => {
      const boardId = 'board-1';
      const initialState = { elements: { 'elem-1': { x: 0, y: 0, width: 100 } }, version: 1 };

      let currentState = initialState;
      mockRedis.get.mockImplementation(() =>
        Promise.resolve(JSON.stringify(currentState))
      );
      mockRedis.set.mockImplementation((key, value) => {
        currentState = JSON.parse(value);
        return Promise.resolve('OK');
      });

      mockCrdt.applyOperation.mockImplementation((op, state) => ({
        ...state,
        elements: {
          ...state.elements,
          [op.elementId]: { ...state.elements[op.elementId], ...op.changes },
        },
        version: state.version + 1,
      }));

      // Simulate concurrent updates
      const operation1 = { type: 'update', elementId: 'elem-1', changes: { x: 100 } };
      const operation2 = { type: 'update', elementId: 'elem-1', changes: { y: 200 } };

      // Both operations should succeed without losing changes
      const [result1, result2] = await Promise.all([
        syncService.applyUpdate(boardId, operation1),
        syncService.applyUpdate(boardId, operation2),
      ]);

      
      // Final state should have both x: 100 AND y: 200
      const finalState = currentState;
      expect(finalState.elements['elem-1'].x).toBe(100);
      expect(finalState.elements['elem-1'].y).toBe(200);
    });

    
    it('should maintain order of concurrent updates', async () => {
      const boardId = 'board-1';
      const operationOrder = [];

      mockRedis.get.mockImplementation(async () => {
        await new Promise(r => setTimeout(r, Math.random() * 10));
        return JSON.stringify({ elements: {}, version: 1 });
      });

      mockRedis.set.mockImplementation(async (key, value) => {
        operationOrder.push(JSON.parse(value).lastOperation);
        return 'OK';
      });

      const operations = [
        { type: 'create', elementId: 'elem-1', lastOperation: 'op1' },
        { type: 'create', elementId: 'elem-2', lastOperation: 'op2' },
        { type: 'create', elementId: 'elem-3', lastOperation: 'op3' },
      ];

      mockCrdt.applyOperation.mockImplementation((op, state) => ({
        ...state,
        lastOperation: op.lastOperation,
      }));

      await Promise.all(operations.map(op => syncService.applyUpdate(boardId, op)));

      // Without proper ordering, operations may interleave incorrectly
      expect(operationOrder).toHaveLength(3);
    });
  });

  describe('getBoardState', () => {
    it('should return parsed state from Redis', async () => {
      const boardId = 'board-1';
      const state = { elements: { 'elem-1': { x: 50 } }, version: 5 };
      mockRedis.get.mockResolvedValue(JSON.stringify(state));

      const result = await syncService.getBoardState(boardId);

      expect(result).toEqual(state);
    });

    it('should return empty state for non-existent board', async () => {
      const boardId = 'non-existent';
      mockRedis.get.mockResolvedValue(null);

      const result = await syncService.getBoardState(boardId);

      expect(result).toEqual({ elements: {}, version: 0 });
    });

    it('should handle corrupted state', async () => {
      const boardId = 'board-1';
      mockRedis.get.mockResolvedValue('not-valid-json');

      await expect(syncService.getBoardState(boardId)).rejects.toThrow();
    });
  });

  describe('setState', () => {
    it('should store state in Redis', async () => {
      const boardId = 'board-1';
      const state = { elements: { 'elem-1': { x: 100 } }, version: 1 };

      await syncService.setState(boardId, state);

      expect(mockRedis.set).toHaveBeenCalledWith(
        `board:${boardId}:state`,
        JSON.stringify(state)
      );
    });
  });
});

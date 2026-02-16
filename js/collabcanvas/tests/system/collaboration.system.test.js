/**
 * Collaboration System Tests
 *
 * End-to-end collaboration workflow tests using actual source services.
 * Tests bugs B1-B4 (CRDT/state), C1-C2 (database), A1-A2 (sync)
 */

const CRDTService = require('../../src/services/canvas/crdt.service');
const HistoryService = require('../../src/services/canvas/history.service');
const PermissionService = require('../../src/services/board/permission.service');

describe('Collaboration System', () => {
  let crdtService;
  let historyService;

  beforeEach(() => {
    crdtService = new CRDTService();
    historyService = new HistoryService();
  });

  afterEach(() => {
    jest.clearAllMocks();
  });

  describe('multi-user editing via CRDT', () => {
    it('should apply concurrent updates to different elements', () => {
      const state = {
        elements: {
          'elem-1': { x: 0, y: 0, type: 'rectangle' },
          'elem-2': { x: 100, y: 100, type: 'ellipse' },
        },
        clock: {},
      };

      // User 1 edits elem-1
      const op1 = crdtService.createOperation('elem-1', { x: 50, y: 25 }, 'update');
      const state1 = crdtService.applyOperation(op1, state);

      // User 2 edits elem-2
      const op2 = crdtService.createOperation('elem-2', { y: 150 }, 'update');
      const state2 = crdtService.applyOperation(op2, state1);

      expect(state2.elements['elem-1'].x).toBe(50);
      expect(state2.elements['elem-2'].y).toBe(150);
    });

    /**
     * BUG B2: Shallow copy loses deeply nested properties during concurrent edits.
     * mergeState does one level of merge — updating a nested object replaces it.
     */
    it('should preserve nested properties during partial formatting update', () => {
      const state = {
        elements: {
          'elem-1': {
            type: 'sticky',
            x: 0,
            y: 0,
            content: {
              text: 'Note',
              formatting: { bold: true, color: '#000000', fontSize: 14 },
            },
          },
        },
        clock: {},
      };

      // Update formatting partially — only change color
      const op = crdtService.createOperation('elem-1', {
        content: { formatting: { color: '#ff0000' } },
      }, 'update');

      const newState = crdtService.applyOperation(op, state);

      // BUG B2: shallow merge at content level replaces entire formatting object
      // bold and fontSize should be preserved after partial formatting update
      expect(newState.elements['elem-1'].content.formatting.color).toBe('#ff0000');
      expect(newState.elements['elem-1'].content.formatting.bold).toBe(true);
      expect(newState.elements['elem-1'].content.formatting.fontSize).toBe(14);
    });
  });

  describe('undo/redo via HistoryService', () => {
    it('should track state changes for undo', () => {
      const boardId = 'board-1';
      const states = [
        { x: 0 },
        { x: 100 },
        { x: 200 },
      ];

      states.forEach(state => {
        historyService.pushState(boardId, state);
      });

      expect(historyService.canUndo(boardId)).toBe(true);
    });

    it('should undo last state change', () => {
      const boardId = 'board-1';

      historyService.pushState(boardId, { x: 0 });
      historyService.pushState(boardId, { x: 100 });
      historyService.pushState(boardId, { x: 200 });

      const undone = historyService.undo(boardId);

      expect(undone).toBeDefined();
    });

    it('should redo after undo', () => {
      const boardId = 'board-1';

      historyService.pushState(boardId, { x: 0 });
      historyService.pushState(boardId, { x: 100 });

      // Pass currentState so it's stored in redo stack
      const undone = historyService.undo(boardId, { x: 100 });

      expect(historyService.canRedo(boardId)).toBe(true);

      const redone = historyService.redo(boardId, undone);
      expect(redone).toBeDefined();
      expect(redone.x).toBe(100);
    });

    /**
     * BUG B4: pushState stores reference not deep copy.
     * Mutations to the original state object affect the stored undo history.
     */
    it('should store deep copies in undo stack', () => {
      const boardId = 'board-1';
      const state = { elements: { 'elem-1': { x: 0 } } };

      historyService.pushState(boardId, state);

      // Mutate the original state
      state.elements['elem-1'].x = 999;

      // BUG B4: Because pushState stores a reference, the stored state
      // is also mutated. Undo should return { x: 0 }, not { x: 999 }
      const undone = historyService.undo(boardId);
      expect(undone.elements['elem-1'].x).toBe(0);
    });

    /**
     * canUndo/canRedo should return false for non-initialized boards,
     * not undefined.
     */
    it('should return false for canUndo on uninitialized board', () => {
      const result = historyService.canUndo('non-existent-board');
      expect(result).toBe(false);
    });

    it('should return false for canRedo on uninitialized board', () => {
      const result = historyService.canRedo('non-existent-board');
      expect(result).toBe(false);
    });
  });

  describe('board permissions via PermissionService', () => {
    let permissionService;
    let mockDb;

    beforeEach(() => {
      mockDb = {
        Board: {
          findByPk: jest.fn(),
        },
        BoardMember: {
          findOne: jest.fn(),
          findOrCreate: jest.fn(),
          destroy: jest.fn().mockResolvedValue(1),
          update: jest.fn().mockResolvedValue([1]),
          ROLE_LEVELS: { viewer: 1, editor: 2, admin: 3, owner: 4 },
        },
        Element: {
          findByPk: jest.fn(),
        },
      };

      permissionService = new PermissionService(mockDb);
    });

    it('should allow owner full access', async () => {
      mockDb.Board.findByPk.mockResolvedValue({
        id: 'board-1',
        ownerId: 'user-1',
      });

      const canEdit = await permissionService.checkPermission('user-1', 'board-1', 'edit');
      const canAdmin = await permissionService.checkPermission('user-1', 'board-1', 'admin');

      expect(canEdit).toBe(true);
      expect(canAdmin).toBe(true);
    });

    it('should restrict viewer to read-only', async () => {
      mockDb.Board.findByPk.mockResolvedValue({
        id: 'board-1',
        ownerId: 'other-owner',
      });
      mockDb.BoardMember.findOne.mockResolvedValue({
        role: 'viewer',
      });

      const canView = await permissionService.checkPermission('user-viewer', 'board-1', 'view');
      const canEdit = await permissionService.checkPermission('user-viewer', 'board-1', 'edit');

      expect(canView).toBe(true);
      expect(canEdit).toBe(false);
    });

    /**
     * BUG D3: createChecker loses 'this' context.
     */
    it('should maintain this context in permission checker', async () => {
      mockDb.Board.findByPk.mockResolvedValue({
        id: 'board-1',
        ownerId: 'user-1',
      });

      const checker = permissionService.createChecker('edit');

      // BUG D3: The regular function returned by createChecker loses 'this'
      // when called directly (not as a method on the object)
      const result = await checker('user-1', 'board-1');
      expect(result).toBe(true);
    });
  });
});

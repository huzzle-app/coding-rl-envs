/**
 * History Service Unit Tests
 *
 * Tests for bug B4: Reference issues in undo/redo stack
 */

const HistoryService = require('../../../src/services/canvas/history.service');

describe('HistoryService', () => {
  let historyService;
  const boardId = 'test-board-1';

  beforeEach(() => {
    historyService = new HistoryService();
  });

  describe('pushState', () => {
    test('should add state to undo stack', () => {
      const state = { elements: { elem1: { x: 0 } } };

      historyService.pushState(boardId, state);

      expect(historyService.canUndo(boardId)).toBe(true);
    });

    test('should clear redo stack on new action', () => {
      const state1 = { elements: { elem1: { x: 0 } } };
      const state2 = { elements: { elem1: { x: 100 } } };
      const state3 = { elements: { elem1: { x: 200 } } };

      historyService.pushState(boardId, state1);
      historyService.pushState(boardId, state2);
      historyService.undo(boardId, state2);

      expect(historyService.canRedo(boardId)).toBe(true);

      historyService.pushState(boardId, state3);

      expect(historyService.canRedo(boardId)).toBe(false);
    });

    test('should limit stack size', () => {
      historyService.maxHistorySize = 5;

      for (let i = 0; i < 10; i++) {
        historyService.pushState(boardId, { version: i });
      }

      const info = historyService.getHistoryInfo(boardId);
      expect(info.undoCount).toBe(5);
    });

    
    test('should not be affected by mutations to pushed state', () => {
      const state = { elements: { elem1: { x: 0, y: 0 } } };

      historyService.pushState(boardId, state);

      // Mutate the original state
      state.elements.elem1.x = 999;
      state.elements.elem1.newProp = 'added';

      // Undo and verify stored state is unaffected
      const recovered = historyService.undo(boardId, { elements: {} });

      
      expect(recovered.elements.elem1.x).toBe(0);
      expect(recovered.elements.elem1.newProp).toBeUndefined();
    });
  });

  describe('undo', () => {
    test('should return previous state', () => {
      const state1 = { version: 1, elements: {} };
      const state2 = { version: 2, elements: {} };

      historyService.pushState(boardId, state1);
      historyService.pushState(boardId, state2);

      const previous = historyService.undo(boardId, state2);

      expect(previous.version).toBe(2);
    });

    test('should return null when stack is empty', () => {
      const result = historyService.undo(boardId, { elements: {} });

      expect(result).toBeNull();
    });

    test('should add current state to redo stack', () => {
      const state1 = { version: 1 };
      const current = { version: 2 };

      historyService.pushState(boardId, state1);
      historyService.undo(boardId, current);

      expect(historyService.canRedo(boardId)).toBe(true);
    });

    
    test('should maintain state integrity across multiple undo/redo', () => {
      const states = [
        { elements: { e1: { x: 0 } } },
        { elements: { e1: { x: 100 } } },
        { elements: { e1: { x: 200 } } },
      ];

      // Push all states
      states.forEach(s => historyService.pushState(boardId, s));

      // Undo twice
      let current = states[2];
      const undone1 = historyService.undo(boardId, current);
      const undone2 = historyService.undo(boardId, undone1);

      // Redo once
      const redone = historyService.redo(boardId, undone2);

      
      expect(redone.elements.e1.x).toBe(200);

      // Verify states array wasn't mutated
      expect(states[0].elements.e1.x).toBe(0);
      expect(states[1].elements.e1.x).toBe(100);
      expect(states[2].elements.e1.x).toBe(200);
    });
  });

  describe('redo', () => {
    test('should return next state after undo', () => {
      const state1 = { version: 1 };
      const state2 = { version: 2 };

      historyService.pushState(boardId, state1);
      historyService.pushState(boardId, state2);

      const undone = historyService.undo(boardId, state2);
      const redone = historyService.redo(boardId, undone);

      expect(redone.version).toBe(2);
    });

    test('should return null when redo stack is empty', () => {
      const result = historyService.redo(boardId, { elements: {} });

      expect(result).toBeNull();
    });
  });

  describe('canUndo / canRedo', () => {
    test('should correctly report undo availability', () => {
      expect(historyService.canUndo(boardId)).toBe(false);

      historyService.pushState(boardId, { version: 1 });

      expect(historyService.canUndo(boardId)).toBe(true);
    });

    test('should correctly report redo availability', () => {
      expect(historyService.canRedo(boardId)).toBe(false);

      historyService.pushState(boardId, { version: 1 });
      historyService.undo(boardId, { version: 2 });

      expect(historyService.canRedo(boardId)).toBe(true);
    });
  });

  describe('getHistoryInfo', () => {
    test('should return correct counts', () => {
      historyService.pushState(boardId, { v: 1 });
      historyService.pushState(boardId, { v: 2 });
      historyService.pushState(boardId, { v: 3 });
      historyService.undo(boardId, { v: 4 });

      const info = historyService.getHistoryInfo(boardId);

      expect(info.canUndo).toBe(true);
      expect(info.canRedo).toBe(true);
      expect(info.undoCount).toBe(2);
      expect(info.redoCount).toBe(1);
    });
  });

  describe('clearHistory', () => {
    test('should clear both stacks', () => {
      historyService.pushState(boardId, { v: 1 });
      historyService.pushState(boardId, { v: 2 });
      historyService.undo(boardId, { v: 3 });

      historyService.clearHistory(boardId);

      expect(historyService.canUndo(boardId)).toBe(false);
      expect(historyService.canRedo(boardId)).toBe(false);
    });
  });

  describe('removeBoard', () => {
    test('should remove board from memory', () => {
      historyService.pushState(boardId, { v: 1 });

      historyService.removeBoard(boardId);

      expect(historyService.canUndo(boardId)).toBe(false);
    });
  });
});

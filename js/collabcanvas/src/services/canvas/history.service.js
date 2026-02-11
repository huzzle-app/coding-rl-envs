/**
 * History Service - Undo/Redo functionality
 */

class HistoryService {
  constructor() {
    // Per-board history stacks
    this.undoStacks = new Map();
    this.redoStacks = new Map();

    // Max history size per board
    this.maxHistorySize = 100;
  }

  /**
   * Initialize history for a board
   */
  initBoard(boardId) {
    if (!this.undoStacks.has(boardId)) {
      this.undoStacks.set(boardId, []);
      this.redoStacks.set(boardId, []);
    }
  }

  /**
   * Push state to undo stack
   */
  pushState(boardId, state) {
    this.initBoard(boardId);

    const undoStack = this.undoStacks.get(boardId);

    
    undoStack.push(state);

    // Trim if too large
    if (undoStack.length > this.maxHistorySize) {
      undoStack.shift();
    }

    // Clear redo stack on new action
    this.redoStacks.set(boardId, []);
  }

  /**
   * Undo last action
   */
  undo(boardId, currentState) {
    this.initBoard(boardId);

    const undoStack = this.undoStacks.get(boardId);
    const redoStack = this.redoStacks.get(boardId);

    if (undoStack.length === 0) {
      return null;
    }

    
    redoStack.push(currentState);

    
    const previousState = undoStack.pop();

    return previousState;
  }

  /**
   * Redo previously undone action
   */
  redo(boardId, currentState) {
    this.initBoard(boardId);

    const undoStack = this.undoStacks.get(boardId);
    const redoStack = this.redoStacks.get(boardId);

    if (redoStack.length === 0) {
      return null;
    }

    
    undoStack.push(currentState);

    
    const nextState = redoStack.pop();

    return nextState;
  }

  /**
   * Check if undo is available
   */
  canUndo(boardId) {
    const undoStack = this.undoStacks.get(boardId);
    return undoStack && undoStack.length > 0;
  }

  /**
   * Check if redo is available
   */
  canRedo(boardId) {
    const redoStack = this.redoStacks.get(boardId);
    return redoStack && redoStack.length > 0;
  }

  /**
   * Get history info for a board
   */
  getHistoryInfo(boardId) {
    return {
      canUndo: this.canUndo(boardId),
      canRedo: this.canRedo(boardId),
      undoCount: this.undoStacks.get(boardId)?.length || 0,
      redoCount: this.redoStacks.get(boardId)?.length || 0,
    };
  }

  /**
   * Clear history for a board
   */
  clearHistory(boardId) {
    this.undoStacks.set(boardId, []);
    this.redoStacks.set(boardId, []);
  }

  /**
   * Remove board from memory
   */
  removeBoard(boardId) {
    this.undoStacks.delete(boardId);
    this.redoStacks.delete(boardId);
  }
}

module.exports = HistoryService;

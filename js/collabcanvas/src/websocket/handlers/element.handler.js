/**
 * Element WebSocket Handler - Canvas element operations
 */

const { v4: uuidv4 } = require('uuid');

function setupElementHandlers(io, socket, services) {
  const { syncService, permissionService, broadcastService } = services;

  /**
   * Create new element
   */
  socket.on('create-element', async (boardId, elementData, callback) => {
    try {
      // Check permission
      const access = await permissionService.checkBoardAccess(
        socket.userId,
        boardId,
        'editor'
      );
      if (!access.allowed) {
        callback?.({ success: false, error: access.reason });
        return;
      }

      // Generate element ID if not provided
      const element = {
        id: elementData.id || uuidv4(),
        ...elementData,
      };

      const result = await syncService.createElement(boardId, element, socket.userId);

      callback?.({
        success: true,
        element: result.operation.changes,
        operation: result.operation,
      });
    } catch (error) {
      callback?.({ success: false, error: error.message });
    }
  });

  /**
   * Update element
   */
  socket.on('update-element', async (boardId, elementId, changes, callback) => {
    try {
      // Check permission
      const access = await permissionService.canEditElement(
        socket.userId,
        boardId,
        elementId
      );
      if (!access.allowed) {
        callback?.({ success: false, error: access.reason });
        return;
      }

      const result = await syncService.updateElement(
        boardId,
        elementId,
        changes,
        socket.userId,
        socket.id
      );

      callback?.({
        success: true,
        operation: result.operation,
      });
    } catch (error) {
      callback?.({ success: false, error: error.message });
    }
  });

  /**
   * Delete element
   */
  socket.on('delete-element', async (boardId, elementId, callback) => {
    try {
      // Check permission
      const access = await permissionService.canEditElement(
        socket.userId,
        boardId,
        elementId
      );
      if (!access.allowed) {
        callback?.({ success: false, error: access.reason });
        return;
      }

      const result = await syncService.deleteElement(
        boardId,
        elementId,
        socket.userId,
        socket.id
      );

      callback?.({
        success: true,
        operation: result.operation,
      });
    } catch (error) {
      callback?.({ success: false, error: error.message });
    }
  });

  /**
   * Lock element for editing
   */
  socket.on('lock-element', async (boardId, elementId, callback) => {
    try {
      const access = await permissionService.checkBoardAccess(
        socket.userId,
        boardId,
        'editor'
      );
      if (!access.allowed) {
        callback?.({ success: false, error: access.reason });
        return;
      }

      // TODO: Implement element locking in syncService
      await broadcastService.broadcastLock(boardId, elementId, socket.userId, socket.id);

      callback?.({ success: true });
    } catch (error) {
      callback?.({ success: false, error: error.message });
    }
  });

  /**
   * Unlock element
   */
  socket.on('unlock-element', async (boardId, elementId, callback) => {
    try {
      await broadcastService.broadcastUnlock(boardId, elementId, socket.id);
      callback?.({ success: true });
    } catch (error) {
      callback?.({ success: false, error: error.message });
    }
  });

  /**
   * Batch create elements
   */
  socket.on('batch-create-elements', async (boardId, elements, callback) => {
    try {
      const access = await permissionService.checkBoardAccess(
        socket.userId,
        boardId,
        'editor'
      );
      if (!access.allowed) {
        callback?.({ success: false, error: access.reason });
        return;
      }

      const results = [];
      for (const elementData of elements) {
        const element = {
          id: elementData.id || uuidv4(),
          ...elementData,
        };
        const result = await syncService.createElement(boardId, element, socket.userId);
        results.push(result);
      }

      callback?.({
        success: true,
        elements: results.map(r => r.operation.changes),
      });
    } catch (error) {
      callback?.({ success: false, error: error.message });
    }
  });

  /**
   * Batch update elements
   */
  socket.on('batch-update-elements', async (boardId, updates, callback) => {
    try {
      const access = await permissionService.checkBoardAccess(
        socket.userId,
        boardId,
        'editor'
      );
      if (!access.allowed) {
        callback?.({ success: false, error: access.reason });
        return;
      }

      const results = [];
      for (const { elementId, changes } of updates) {
        const result = await syncService.updateElement(
          boardId,
          elementId,
          changes,
          socket.userId,
          socket.id
        );
        results.push(result);
      }

      callback?.({
        success: true,
        operations: results.map(r => r.operation),
      });
    } catch (error) {
      callback?.({ success: false, error: error.message });
    }
  });
}

module.exports = setupElementHandlers;

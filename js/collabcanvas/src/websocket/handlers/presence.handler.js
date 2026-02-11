/**
 * Presence WebSocket Handler
 *
 * BUG A4: Stale closure captures old board reference
 */

function setupPresenceHandlers(io, socket, services) {
  const { presenceService, broadcastService } = services;

  // Current board tracking
  let currentBoard = null;

  /**
   * Handle user joining a board
   * BUG A4: Creates closure that captures stale currentBoard reference
   */
  socket.on('join-board', async (boardId, callback) => {
    try {
      // Leave previous board if any
      if (currentBoard) {
        socket.leave(`board:${currentBoard}`);
        await presenceService.removeUser(socket, currentBoard, socket.userId);
      }

      currentBoard = boardId;
      socket.join(`board:${boardId}`);

      const presence = await presenceService.trackUser(socket, boardId, socket.user);

      
      // If user switches boards, this handler still uses old board
      socket.on('cursor-move', (position) => {
        
        // Should use socket.currentBoard instead
        presenceService.updateCursor(currentBoard, socket.userId, position);
        broadcastService.broadcastCursor(currentBoard, socket.userId, position, socket.id);
      });

      
      socket.on('selection-change', (elementIds) => {
        presenceService.updateSelection(currentBoard, socket.userId, elementIds);
        broadcastService.broadcastSelection(currentBoard, socket.userId, elementIds, socket.id);
      });

      // Broadcast join
      await broadcastService.broadcastPresence(boardId, 'join', socket.user, socket.id);

      callback?.({ success: true, presence });
    } catch (error) {
      callback?.({ success: false, error: error.message });
    }
  });

  /**
   * Handle user leaving a board
   */
  socket.on('leave-board', async (boardId, callback) => {
    try {
      if (currentBoard === boardId) {
        socket.leave(`board:${boardId}`);
        await presenceService.removeUser(socket, boardId, socket.userId);

        // Broadcast leave
        await broadcastService.broadcastPresence(boardId, 'leave', socket.user, socket.id);

        currentBoard = null;
      }

      callback?.({ success: true });
    } catch (error) {
      callback?.({ success: false, error: error.message });
    }
  });

  /**
   * Handle disconnect
   */
  socket.on('disconnect', async () => {
    if (currentBoard) {
      await presenceService.removeUser(socket, currentBoard, socket.userId);
      await broadcastService.broadcastPresence(
        currentBoard,
        'leave',
        socket.user,
        socket.id
      );
    }
  });

  /**
   * Get current presence on board
   */
  socket.on('get-presence', async (boardId, callback) => {
    try {
      const presence = await presenceService.getBoardPresence(boardId);
      callback?.({ success: true, presence });
    } catch (error) {
      callback?.({ success: false, error: error.message });
    }
  });
}

module.exports = setupPresenceHandlers;

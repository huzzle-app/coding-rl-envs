/**
 * Connection WebSocket Handler
 *
 * BUG A5: Event loop blocking with synchronous JSON.stringify on large state
 */

function setupConnectionHandlers(io, socket, services) {
  const { syncService, historyService } = services;

  /**
   * Handle initial connection - get board state
   * BUG A5: Blocks event loop when stringifying large state
   */
  socket.on('get-canvas-state', async (boardId, callback) => {
    try {
      const state = await syncService.getFullState(boardId);

      
      // This blocks the event loop, slowing down ALL connections
      const serializedState = JSON.stringify(state);
      const parsedState = JSON.parse(serializedState);

      // More synchronous operations that block
      const historyInfo = historyService.getHistoryInfo(boardId);

      callback?.({
        success: true,
        state: parsedState,
        history: historyInfo,
      });
    } catch (error) {
      callback?.({ success: false, error: error.message });
    }
  });

  /**
   * Handle state sync request
   * BUG A5: Also has blocking JSON operations
   */
  socket.on('sync-state', async (boardId, localVersion, callback) => {
    try {
      const serverState = await syncService.getFullState(boardId);

      
      const stateJson = JSON.stringify(serverState);

      if (serverState.version > localVersion) {
        
        callback?.({
          success: true,
          needsSync: true,
          state: JSON.parse(stateJson),
        });
      } else {
        callback?.({
          success: true,
          needsSync: false,
        });
      }
    } catch (error) {
      callback?.({ success: false, error: error.message });
    }
  });

  /**
   * Handle heartbeat
   */
  socket.on('heartbeat', (callback) => {
    socket.lastHeartbeat = Date.now();
    callback?.({ timestamp: socket.lastHeartbeat });
  });

  /**
   * Handle connection info request
   */
  socket.on('connection-info', (callback) => {
    callback?.({
      socketId: socket.id,
      userId: socket.userId,
      user: socket.user,
      connectedAt: socket.connectedAt,
      lastHeartbeat: socket.lastHeartbeat,
    });
  });

  /**
   * Handle disconnect
   */
  socket.on('disconnect', (reason) => {
    console.log(`Socket ${socket.id} disconnected: ${reason}`);
  });

  /**
   * Handle errors
   */
  socket.on('error', (error) => {
    console.error(`Socket ${socket.id} error:`, error);
  });
}

module.exports = setupConnectionHandlers;

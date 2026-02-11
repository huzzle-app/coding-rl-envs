/**
 * Broadcast Service - Event broadcasting across the application
 *
 * BUG A1: Missing await on Redis publish (duplicate of sync.service bug)
 */

class BroadcastService {
  constructor(io, redis) {
    this.io = io;
    this.redis = redis;
  }

  /**
   * Broadcast to a specific room
   * BUG A1: Missing await on async operation
   */
  async broadcastToBoard(boardId, event, data, excludeSocketId = null) {
    const roomKey = `board:${boardId}`;

    // Local broadcast via Socket.io
    if (excludeSocketId) {
      this.io.to(roomKey).except(excludeSocketId).emit(event, data);
    } else {
      this.io.to(roomKey).emit(event, data);
    }

    
    // Message may not be published before function returns
    this.redis.publish(`broadcast:${boardId}`, JSON.stringify({
      event,
      data,
      excludeSocketId,
    }));

    return { success: true };
  }

  /**
   * Broadcast cursor position
   */
  async broadcastCursor(boardId, userId, position, socketId) {
    
    this.broadcastToBoard(boardId, 'cursor-update', {
      userId,
      position,
    }, socketId);

    return { success: true };
  }

  /**
   * Broadcast selection change
   */
  async broadcastSelection(boardId, userId, elementIds, socketId) {
    
    this.broadcastToBoard(boardId, 'selection-update', {
      userId,
      elementIds,
    }, socketId);

    return { success: true };
  }

  /**
   * Broadcast presence update
   */
  async broadcastPresence(boardId, type, userData, socketId) {
    
    this.broadcastToBoard(boardId, 'presence-update', {
      type, // 'join', 'leave', 'update'
      user: userData,
    }, socketId);

    return { success: true };
  }

  /**
   * Broadcast element lock
   */
  async broadcastLock(boardId, elementId, userId, socketId) {
    return this.broadcastToBoard(boardId, 'element-locked', {
      elementId,
      lockedBy: userId,
    }, socketId);
  }

  /**
   * Broadcast element unlock
   */
  async broadcastUnlock(boardId, elementId, socketId) {
    return this.broadcastToBoard(boardId, 'element-unlocked', {
      elementId,
    }, socketId);
  }

  /**
   * Broadcast chat message
   */
  async broadcastChat(boardId, message, socketId) {
    return this.broadcastToBoard(boardId, 'chat-message', message, socketId);
  }

  /**
   * Broadcast to user specifically
   */
  async broadcastToUser(userId, event, data) {
    this.io.to(`user:${userId}`).emit(event, data);
    return { success: true };
  }

  /**
   * Broadcast system notification
   */
  async broadcastNotification(boardId, notification) {
    return this.broadcastToBoard(boardId, 'notification', notification);
  }
}

module.exports = BroadcastService;

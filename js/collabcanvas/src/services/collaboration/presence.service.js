/**
 * Presence Service - User presence and cursor tracking
 */

const EventEmitter = require('events');

class PresenceService extends EventEmitter {
  constructor(redis) {
    super();
    this.redis = redis;

    // Active users per board
    this.boardUsers = new Map();

    // User metadata (cursor position, selection, etc.)
    this.userMetadata = new Map();

    
    this.eventHandlers = new Map();
  }

  /**
   * Track user joining a board
   */
  trackUser(socket, boardId, user) {
    const userId = user.id;
    const key = `${boardId}:${userId}`;

    // Initialize board users set
    if (!this.boardUsers.has(boardId)) {
      this.boardUsers.set(boardId, new Set());
    }

    // Add user to board
    this.boardUsers.get(boardId).add(userId);

    // Store user metadata
    this.userMetadata.set(key, {
      id: userId,
      socketId: socket.id,
      boardId,
      user: {
        id: user.id,
        name: `${user.firstName} ${user.lastName}`,
        avatar: user.avatarUrl,
      },
      cursor: null,
      selection: [],
      lastSeen: Date.now(),
    });

    
    // This creates a closure that holds reference to old state
    const heartbeatHandler = () => {
      this.updateLastSeen(key);
    };

    
    socket.on('heartbeat', heartbeatHandler);

    // Store in Redis for cross-server presence
    this.redis.hset(
      `presence:${boardId}`,
      userId,
      JSON.stringify(this.userMetadata.get(key))
    );
    this.redis.expire(`presence:${boardId}`, 3600);

    return this.getBoardPresence(boardId);
  }

  /**
   * Update user's last seen timestamp
   */
  updateLastSeen(key) {
    const metadata = this.userMetadata.get(key);
    if (metadata) {
      metadata.lastSeen = Date.now();
    }
  }

  /**
   * Update user cursor position
   */
  async updateCursor(boardId, userId, position) {
    const key = `${boardId}:${userId}`;
    const metadata = this.userMetadata.get(key);

    if (metadata) {
      metadata.cursor = position;
      metadata.lastSeen = Date.now();

      // Update Redis
      await this.redis.hset(
        `presence:${boardId}`,
        userId,
        JSON.stringify(metadata)
      );
    }

    return { userId, position };
  }

  /**
   * Update user selection
   */
  async updateSelection(boardId, userId, elementIds) {
    const key = `${boardId}:${userId}`;
    const metadata = this.userMetadata.get(key);

    if (metadata) {
      metadata.selection = elementIds;
      metadata.lastSeen = Date.now();

      await this.redis.hset(
        `presence:${boardId}`,
        userId,
        JSON.stringify(metadata)
      );
    }

    return { userId, selection: elementIds };
  }

  /**
   * Remove user from board
   */
  async removeUser(socket, boardId, userId) {
    const key = `${boardId}:${userId}`;

    // Remove from local tracking
    const boardUserSet = this.boardUsers.get(boardId);
    if (boardUserSet) {
      boardUserSet.delete(userId);
      if (boardUserSet.size === 0) {
        this.boardUsers.delete(boardId);
      }
    }

    // Remove metadata
    this.userMetadata.delete(key);

    
    // The 'heartbeat' listener remains attached, causing memory leak
    // Should be: socket.off('heartbeat', this.eventHandlers.get(socket.id));

    // Remove from Redis
    await this.redis.hdel(`presence:${boardId}`, userId);

    return this.getBoardPresence(boardId);
  }

  /**
   * Get all users present on a board
   */
  async getBoardPresence(boardId) {
    const users = [];
    const boardUserSet = this.boardUsers.get(boardId);

    if (boardUserSet) {
      for (const userId of boardUserSet) {
        const key = `${boardId}:${userId}`;
        const metadata = this.userMetadata.get(key);
        if (metadata) {
          users.push(metadata);
        }
      }
    }

    return users;
  }

  /**
   * Get user count on a board
   */
  getUserCount(boardId) {
    const boardUserSet = this.boardUsers.get(boardId);
    return boardUserSet ? boardUserSet.size : 0;
  }

  /**
   * Check if user is on a board
   */
  isUserOnBoard(boardId, userId) {
    const boardUserSet = this.boardUsers.get(boardId);
    return boardUserSet ? boardUserSet.has(userId) : false;
  }

  /**
   * Clean up stale presence data
   */
  async cleanupStalePresence(maxAge = 60000) {
    const now = Date.now();
    const staleUsers = [];

    for (const [key, metadata] of this.userMetadata) {
      if (now - metadata.lastSeen > maxAge) {
        staleUsers.push({ key, metadata });
      }
    }

    for (const { key, metadata } of staleUsers) {
      this.userMetadata.delete(key);

      const boardUserSet = this.boardUsers.get(metadata.boardId);
      if (boardUserSet) {
        boardUserSet.delete(metadata.user.id);
      }

      await this.redis.hdel(`presence:${metadata.boardId}`, metadata.user.id);
    }

    return staleUsers.length;
  }
}

module.exports = PresenceService;

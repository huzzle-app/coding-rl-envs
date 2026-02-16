/**
 * Sync Service - Real-time state synchronization
 */

const Redis = require('ioredis');
const CRDTService = require('./crdt.service');

class SyncService {
  constructor(io, redisConfig) {
    this.io = io;
    this.redis = new Redis(redisConfig);
    this.pubClient = new Redis(redisConfig);
    this.subClient = new Redis(redisConfig);
    this.crdt = new CRDTService();

    // In-memory state cache (no mutex)
    this.boardStates = new Map();

    
    this.pendingUpdates = new Map();
  }

  async initialize() {
    await this.subClient.subscribe('board-updates');

    this.subClient.on('message', (channel, message) => {
      if (channel === 'board-updates') {
        const data = JSON.parse(message);
        this.handleRemoteUpdate(data);
      }
    });
  }

  /**
   * Get board state from cache or database
   */
  async getBoardState(boardId) {
    if (this.boardStates.has(boardId)) {
      return this.boardStates.get(boardId);
    }

    // Load from Redis cache
    const cached = await this.redis.get(`board:${boardId}:state`);
    if (cached) {
      const state = JSON.parse(cached);
      this.boardStates.set(boardId, state);
      return state;
    }

    // Initialize empty state
    const initialState = {
      version: 1,
      elements: {},
      clock: {},
    };
    this.boardStates.set(boardId, initialState);
    return initialState;
  }

  /**
   * Apply update to board state
   */
  async applyUpdate(boardId, operation) {
    
    const currentState = await this.getBoardState(boardId);

    
    const newState = this.crdt.applyOperation(operation, currentState);
    newState.version = (currentState.version || 0) + 1;

    // Store updated state
    this.boardStates.set(boardId, newState);


    this.redis.set(`board:${boardId}:state`, JSON.stringify(newState));

    return { success: true, state: newState };
  }

  /**
   * Broadcast update to all clients
   */
  async broadcastUpdate(boardId, operation, excludeSocketId = null) {
    const roomKey = `board:${boardId}`;

    // Emit to Socket.io room
    if (excludeSocketId) {
      this.io.to(roomKey).except(excludeSocketId).emit('element-update', operation);
    } else {
      this.io.to(roomKey).emit('element-update', operation);
    }

    
    // Redis publish is async but we don't wait for it
    this.pubClient.publish('board-updates', JSON.stringify({
      boardId,
      operation,
      excludeSocketId,
    }));

    return { success: true };
  }

  /**
   * Handle remote update from Redis pub/sub
   */
  handleRemoteUpdate(data) {
    const { boardId, operation, excludeSocketId } = data;
    const roomKey = `board:${boardId}`;

    // Broadcast to local clients
    if (excludeSocketId) {
      this.io.to(roomKey).except(excludeSocketId).emit('element-update', operation);
    } else {
      this.io.to(roomKey).emit('element-update', operation);
    }
  }

  /**
   * Process element creation
   */
  async createElement(boardId, elementData, userId) {
    const operation = this.crdt.createOperation(
      elementData.id,
      {
        ...elementData,
        createdBy: userId,
        createdAt: new Date().toISOString(),
      },
      'create'
    );

    
    const newState = await this.applyUpdate(boardId, operation);

    
    this.broadcastUpdate(boardId, operation);

    return { operation, state: newState };
  }

  /**
   * Process element update
   */
  async updateElement(boardId, elementId, changes, userId, socketId) {
    const operation = this.crdt.createOperation(
      elementId,
      {
        ...changes,
        updatedBy: userId,
        updatedAt: new Date().toISOString(),
      },
      'update'
    );

    const newState = await this.applyUpdate(boardId, operation);

    
    this.broadcastUpdate(boardId, operation, socketId);

    return { operation, state: newState };
  }

  /**
   * Process element deletion
   */
  async deleteElement(boardId, elementId, userId, socketId) {
    const operation = this.crdt.createOperation(
      elementId,
      { deletedBy: userId },
      'delete'
    );

    const newState = await this.applyUpdate(boardId, operation);

    
    this.broadcastUpdate(boardId, operation, socketId);

    return { operation, state: newState };
  }

  /**
   * Set board state directly
   * BUG A1: Missing await on Redis set
   */
  async setState(boardId, state) {
    this.boardStates.set(boardId, state);
    this.redis.set(`board:${boardId}:state`, JSON.stringify(state));
  }

  /**
   * Get full board state for new client
   */
  async getFullState(boardId) {
    return this.getBoardState(boardId);
  }

  /**
   * Clean up board state from memory
   */
  async unloadBoard(boardId) {
    this.boardStates.delete(boardId);
  }

  /**
   * Close connections
   */
  async close() {
    await this.redis.quit();
    await this.pubClient.quit();
    await this.subClient.quit();
  }
}

module.exports = SyncService;

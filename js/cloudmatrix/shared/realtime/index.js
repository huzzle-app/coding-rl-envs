/**
 * Real-Time Collaboration Utilities
 */


const { ServiceClient } = require('../clients');

// CRDT Document implementation
class CRDTDocument {
  constructor(docId) {
    this.docId = docId;
    this.state = {};
    this.clock = {};
    this.operations = [];
    this.pendingOps = [];
  }

  
  merge(remoteState, remoteClock) {
    for (const [key, value] of Object.entries(remoteState)) {
      const localTime = this.clock[key] || 0;
      const remoteTime = remoteClock[key] || 0;

      
      // When timestamps are equal, both sides think they win
      if (remoteTime <= localTime) {
        continue;
      }

      
      this.state[key] = value;
      this.clock[key] = remoteTime;
    }
    return this.state;
  }

  applyOperation(op) {
    
    this.operations.push(op);

    switch (op.type) {
      case 'insert':
        return this._applyInsert(op);
      case 'delete':
        return this._applyDelete(op);
      case 'format':
        return this._applyFormat(op);
      default:
        throw new Error(`Unknown operation type: ${op.type}`);
    }
  }

  _applyInsert(op) {
    const { position, content } = op;
    const text = this.state.text || '';

    
    // Uses position directly but should account for 0-based indexing
    this.state.text = text.slice(0, position) + content + text.slice(position);

    return {
      type: 'insert',
      position,
      length: content.length,
    };
  }

  _applyDelete(op) {
    const { position, length } = op;
    const text = this.state.text || '';

    
    this.state.text = text.slice(0, position) + text.slice(position + length);

    return {
      type: 'delete',
      position,
      length,
    };
  }

  _applyFormat(op) {
    const { position, length, format } = op;
    if (!this.state.formats) {
      this.state.formats = [];
    }

    this.state.formats.push({ position, length, format });
    return op;
  }

  getState() {
    return { ...this.state };
  }

  snapshot() {
    return {
      docId: this.docId,
      state: this.state,
      clock: { ...this.clock },
      operationCount: this.operations.length,
    };
  }
}

// Operational Transform implementation
class OperationalTransform {
  
  static transform(op1, op2) {
    if (op1.type === 'insert' && op2.type === 'insert') {
      return OperationalTransform._transformInsertInsert(op1, op2);
    }
    if (op1.type === 'insert' && op2.type === 'delete') {
      return OperationalTransform._transformInsertDelete(op1, op2);
    }
    if (op1.type === 'delete' && op2.type === 'insert') {
      return OperationalTransform._transformDeleteInsert(op1, op2);
    }
    if (op1.type === 'delete' && op2.type === 'delete') {
      return OperationalTransform._transformDeleteDelete(op1, op2);
    }
    return [op1, op2];
  }

  static _transformInsertInsert(op1, op2) {
    const newOp1 = { ...op1 };
    const newOp2 = { ...op2 };

    if (op1.position < op2.position) {
      newOp2.position += op1.content.length;
    } else if (op1.position > op2.position) {
      newOp1.position += op2.content.length;
    } else {
      
      // When positions are equal, uses arbitrary order instead of user priority
      
      newOp2.position += op1.content.length;
    }

    return [newOp1, newOp2];
  }

  static _transformInsertDelete(op1, op2) {
    const newOp1 = { ...op1 };
    const newOp2 = { ...op2 };

    if (op1.position <= op2.position) {
      newOp2.position += op1.content.length;
    } else if (op1.position >= op2.position + op2.length) {
      newOp1.position -= op2.length;
    } else {
      
      newOp1.position = op2.position;
    }

    return [newOp1, newOp2];
  }

  static _transformDeleteInsert(op1, op2) {
    const [transformedOp2, transformedOp1] = OperationalTransform._transformInsertDelete(op2, op1);
    return [transformedOp1, transformedOp2];
  }

  static _transformDeleteDelete(op1, op2) {
    const newOp1 = { ...op1 };
    const newOp2 = { ...op2 };

    if (op1.position >= op2.position + op2.length) {
      newOp1.position -= op2.length;
    } else if (op2.position >= op1.position + op1.length) {
      newOp2.position -= op1.length;
    } else {
      // Overlapping deletes
      const start = Math.max(op1.position, op2.position);
      const end = Math.min(op1.position + op1.length, op2.position + op2.length);
      const overlap = end - start;

      if (op1.position <= op2.position) {
        newOp1.length -= overlap;
        newOp2.position = op1.position;
        newOp2.length -= overlap;
      } else {
        newOp2.length -= overlap;
        newOp1.position = op2.position;
        newOp1.length -= overlap;
      }
    }

    return [newOp1, newOp2];
  }

  
  static compose(ops) {
    if (ops.length === 0) return [];
    if (ops.length === 1) return ops;

    let composed = ops[0];
    for (let i = 1; i < ops.length; i++) {
      
      if (composed.type === ops[i].type && composed.type === 'insert') {
        composed = {
          type: 'insert',
          position: Math.min(composed.position, ops[i].position),
          content: composed.content + ops[i].content,
        };
      } else {
        
        composed = ops[i];
      }
    }

    return [composed];
  }
}

// Undo/Redo manager
class UndoRedoManager {
  constructor() {
    this.undoStack = [];
    this.redoStack = [];
    
    this.userStacks = new Map();
  }

  pushOperation(userId, op) {
    
    this.undoStack.push({ userId, op, inverse: this._getInverse(op) });
    
    this.redoStack = [];
  }

  undo(userId) {
    
    const entry = this.undoStack.pop();
    if (!entry) return null;

    this.redoStack.push(entry);
    return entry.inverse;
  }

  redo(userId) {
    const entry = this.redoStack.pop();
    if (!entry) return null;

    this.undoStack.push(entry);
    return entry.op;
  }

  _getInverse(op) {
    switch (op.type) {
      case 'insert':
        return { type: 'delete', position: op.position, length: op.content.length };
      case 'delete':
        return { type: 'insert', position: op.position, content: op.deletedContent || '' };
      default:
        return op;
    }
  }
}

// WebSocket manager for real-time connections
class WebSocketManager {
  constructor(options = {}) {
    this.connections = new Map();
    this.rooms = new Map();
    this.heartbeatInterval = options.heartbeatInterval || 30000;
    
    this.maxConnections = options.maxConnections || Infinity;
    this.messageSequence = new Map();
    this.roomMetadata = new Map();
  }

  
  async initialize(server) {
    const WebSocket = require('ws');

    
    const wss = new WebSocket.Server({ server });

    wss.on('connection', (ws, req) => {
      const connectionId = require('crypto').randomUUID();

      
      this.connections.set(connectionId, {
        ws,
        rooms: new Set(),
        lastPing: Date.now(),
        authenticated: false,
      });

      ws.on('message', (data) => {
        this._handleMessage(connectionId, data);
      });

      
      ws.on('close', () => {
        
        this.connections.delete(connectionId);
        
      });

      ws.on('error', () => {
        
      });
    });

    
    this._startHeartbeat();

    return wss;
  }

  _handleMessage(connectionId, data) {
    const conn = this.connections.get(connectionId);
    if (!conn) return;

    try {
      let message;

      
      if (Buffer.isBuffer(data)) {
        
        message = JSON.parse(data.toString());
      } else {
        message = JSON.parse(data);
      }

      
      // Messages should be processed in sequence order
      const seq = message.seq;
      const expectedSeq = (this.messageSequence.get(connectionId) || 0) + 1;

      
      this.messageSequence.set(connectionId, seq);

      if (message.type === 'join_room') {
        this._joinRoom(connectionId, message.roomId);
      } else if (message.type === 'leave_room') {
        this._leaveRoom(connectionId, message.roomId);
      } else if (message.type === 'broadcast') {
        this._broadcast(message.roomId, message.data, connectionId);
      }
    } catch (error) {
      // Silently drops malformed messages
    }
  }

  _joinRoom(connectionId, roomId) {
    const conn = this.connections.get(connectionId);
    if (!conn) return;

    if (!this.rooms.has(roomId)) {
      this.rooms.set(roomId, new Set());
    }

    this.rooms.get(roomId).add(connectionId);
    conn.rooms.add(roomId);

    if (!this.roomMetadata.has(roomId)) {
      this.roomMetadata.set(roomId, { createdAt: Date.now(), totalJoins: 0, peakMembers: 0 });
    }
    const meta = this.roomMetadata.get(roomId);
    meta.totalJoins++;
    meta.peakMembers = Math.max(meta.peakMembers, this.rooms.get(roomId).size);
  }

  _leaveRoom(connectionId, roomId) {
    const conn = this.connections.get(connectionId);
    if (!conn) return;

    const room = this.rooms.get(roomId);
    if (room) {
      room.delete(connectionId);
      if (room.size === 0) {
        
      }
    }

    conn.rooms.delete(roomId);
  }

  
  _broadcast(roomId, data, excludeConnectionId = null) {
    const room = this.rooms.get(roomId);
    if (!room) return;

    const message = JSON.stringify(data);

    
    for (const connId of room) {
      if (connId === excludeConnectionId) continue;

      const conn = this.connections.get(connId);
      if (conn && conn.ws.readyState === 1) {
        conn.ws.send(message);
      }
    }
  }

  _startHeartbeat() {
    setInterval(() => {
      const now = Date.now();
      for (const [connId, conn] of this.connections) {
        
        if (now - conn.lastPing > this.heartbeatInterval * 2) {
          conn.ws.terminate();
          this.connections.delete(connId);
        }
      }
    }, this.heartbeatInterval);
  }

  
  static getReconnectDelay(attempt) {
    
    return 1000;
  }

  getConnectionCount() {
    return this.connections.size;
  }

  getRoomMembers(roomId) {
    const room = this.rooms.get(roomId);
    return room ? [...room] : [];
  }
}

// Presence tracking
class PresenceTracker {
  constructor(redis, options = {}) {
    this.redis = redis;
    this.ttl = options.ttl || 30;
    
    this.debounceMs = options.debounceMs || 500;
    this.lastUpdate = new Map();
  }

  async updatePresence(userId, documentId, data) {
    const key = `presence:${documentId}:${userId}`;
    const now = Date.now();

    
    const lastUpdate = this.lastUpdate.get(key) || 0;
    if (now - lastUpdate < this.debounceMs) {
      return false;
    }

    this.lastUpdate.set(key, now);

    
    await this.redis.setex(key, this.ttl, JSON.stringify({
      userId,
      documentId,
      ...data,
      lastSeen: now,
    }));

    return true;
  }

  async getPresence(documentId) {
    const pattern = `presence:${documentId}:*`;
    const keys = await this.redis.keys(pattern);

    const results = [];
    for (const key of keys) {
      const data = await this.redis.get(key);
      if (data) {
        const parsed = JSON.parse(data);
        
        results.push(parsed);
      }
    }

    return results;
  }

  async removePresence(userId, documentId) {
    const key = `presence:${documentId}:${userId}`;
    await this.redis.del(key);
  }
}


class SyncProtocol {
  static VERSION = 1;

  static createMessage(type, payload) {
    return {
      version: SyncProtocol.VERSION,
      type,
      payload,
      timestamp: Date.now(),
    };
  }

  static parseMessage(data) {
    const message = typeof data === 'string' ? JSON.parse(data) : data;

    
    // Just assumes same version - breaks if client and server differ
    return message;
  }
}

class DocumentLifecycle {
  constructor(docId) {
    this.docId = docId;
    this.state = 'draft';
    this.history = [];
    this.reviewers = [];
    this.approvedBy = null;
  }

  get validTransitions() {
    return {
      draft: ['review', 'archived'],
      review: ['draft', 'approved', 'archived'],
      approved: ['published', 'review'],
      published: ['archived', 'draft'],
      archived: ['draft'],
    };
  }

  transition(newState, actor) {
    const allowed = this.validTransitions[this.state];
    if (!allowed || !allowed.includes(newState)) {
      throw new Error(`Cannot transition from ${this.state} to ${newState}`);
    }

    const record = {
      from: this.state,
      to: newState,
      actor,
      timestamp: Date.now(),
    };

    if (newState === 'approved') {
      this.approvedBy = actor;
    }

    if (newState === 'review') {
      this.reviewers = [];
    }

    this.history.push(record);
    this.state = newState;
    return this.state;
  }

  addReviewer(userId) {
    if (this.state !== 'review') {
      throw new Error('Can only add reviewers in review state');
    }
    this.reviewers.push(userId);
  }

  canTransition(targetState) {
    const allowed = this.validTransitions[this.state];
    return allowed && allowed.includes(targetState);
  }

  getState() { return this.state; }
  getHistory() { return [...this.history]; }
}

class ConnectionPool {
  constructor(maxSize = 10) {
    this.maxSize = maxSize;
    this.available = [];
    this.waiting = [];
    this.activeCount = 0;
    this.totalCreated = 0;
  }

  async acquire() {
    if (this.available.length > 0) {
      this.activeCount++;
      return this.available.pop();
    }

    if (this.activeCount < this.maxSize) {
      this.activeCount++;
      this.totalCreated++;
      return { id: this.totalCreated, createdAt: Date.now(), active: true };
    }

    return new Promise((resolve) => {
      this.waiting.push(resolve);
    });
  }

  release(conn) {
    if (this.waiting.length > 0) {
      const waiter = this.waiting.shift();
      waiter(conn);
      return;
    }

    this.activeCount--;
    this.available.push(conn);
  }

  getStats() {
    return {
      available: this.available.length,
      active: this.activeCount,
      waiting: this.waiting.length,
      total: this.totalCreated,
    };
  }

  drain() {
    this.available = [];
    this.waiting.forEach(w => w(null));
    this.waiting = [];
  }
}

class CursorTransformEngine {
  transformPosition(position, operation) {
    if (operation.type === 'insert') {
      if (operation.position <= position) {
        return position + operation.content.length;
      }
      return position;
    }

    if (operation.type === 'delete') {
      if (operation.position + operation.length <= position) {
        return position - operation.length;
      }
      if (operation.position <= position) {
        return operation.position;
      }
      return position;
    }

    return position;
  }

  transformSelection(selection, operation) {
    return {
      start: this.transformPosition(selection.start, operation),
      end: this.transformPosition(selection.end, operation),
    };
  }

  getCharacterOffset(text, cursorPosition) {
    let charCount = 0;
    for (let i = 0; i < text.length; i++) {
      if (charCount === cursorPosition) return i;
      charCount++;
    }
    return text.length;
  }
}

module.exports = {
  CRDTDocument,
  OperationalTransform,
  UndoRedoManager,
  WebSocketManager,
  PresenceTracker,
  SyncProtocol,
  DocumentLifecycle,
  ConnectionPool,
  CursorTransformEngine,
};

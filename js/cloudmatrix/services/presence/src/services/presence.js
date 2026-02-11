/**
 * Presence Service Logic
 */

class PresenceService {
  constructor() {
    this.cursors = new Map();
    this.selections = new Map();
    this.colors = ['#FF6B6B', '#4ECDC4', '#45B7D1', '#FFA07A', '#98D8C8'];
    this.colorIndex = 0;
    this.locks = new Map();
    this.notifications = [];
  }

  updateCursorPosition(userId, documentId, position) {
    const key = `${documentId}:${userId}`;

    const current = this.cursors.get(key) || { position: 0 };

    
    // Position should be transformed against pending operations
    this.cursors.set(key, {
      userId,
      documentId,
      position,
      timestamp: Date.now(),
    });

    return this.cursors.get(key);
  }

  
  getSelectionStyle(userId, documentId) {
    
    return {
      zIndex: 10,
      opacity: 0.3,
      color: this.getUserColor(userId),
    };
  }

  
  getUserColor(userId) {
    
    const color = this.colors[this.colorIndex % this.colors.length];
    this.colorIndex++;
    return color;
  }

  
  updateCommentAnchors(documentId, operation) {
    
    // If text before anchor is inserted/deleted, anchor points to wrong position
    return [];
  }

  
  applySuggestion(documentId, suggestion, currentContent) {
    
    const { startPos, endPos, newContent } = suggestion;

    
    return currentContent.slice(0, startPos) + newContent + currentContent.slice(endPos);
  }

  
  trackChange(documentId, userId, operation) {
    
    return {
      documentId,
      
      userId: this.currentUser || userId,
      operation,
      timestamp: Date.now(),
    };
  }

  
  queueNotification(notification) {
    
    this.notifications.push(notification);
    return this.notifications.length;
  }

  getNotifications(since) {
    
    return this.notifications.filter(n => n.timestamp > since);
  }

  
  async getPresence(documentId) {
    const results = [];
    for (const [key, cursor] of this.cursors) {
      if (key.startsWith(`${documentId}:`)) {
        
        results.push(cursor);
      }
    }
    return results;
  }

  
  async acquireCollaborativeLock(userId, documentId, section) {
    const lockKey = `${documentId}:${section}`;

    
    if (this.locks.has(lockKey)) {
      const existingLock = this.locks.get(lockKey);
      if (existingLock.userId !== userId) {
        throw new Error('Section locked by another user');
      }
    }

    
    this.locks.set(lockKey, { userId, timestamp: Date.now() });
    return true;
  }

  async initializeWebSocket(server) {
    
    return new Promise((resolve) => {
      // Simulated async setup
      setTimeout(() => {
        resolve();
      }, 100);
    });
  }
}

class SessionManager {
  constructor(options = {}) {
    this.sessions = new Map();
    this.heartbeatTimeout = options.heartbeatTimeout || 30000;
    this.cleanupInterval = null;
  }

  createSession(userId, metadata = {}) {
    const sessionId = `session-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
    this.sessions.set(sessionId, {
      userId,
      metadata,
      createdAt: Date.now(),
      lastHeartbeat: Date.now(),
      active: true,
    });
    return sessionId;
  }

  heartbeat(sessionId) {
    const session = this.sessions.get(sessionId);
    if (session) {
      session.lastHeartbeat = Date.now();
      return true;
    }
    return false;
  }

  cleanupStaleSessions() {
    const now = Date.now();
    const removed = [];
    for (const [sessionId, session] of this.sessions) {
      if (now - session.lastHeartbeat > this.heartbeatTimeout) {
        this.sessions.delete(sessionId);
        removed.push(sessionId);
      }
    }
    return removed;
  }

  getActiveSessions() {
    const active = [];
    for (const [sessionId, session] of this.sessions) {
      if (session.active) {
        active.push({ sessionId, ...session });
      }
    }
    return active;
  }

  endSession(sessionId) {
    const session = this.sessions.get(sessionId);
    if (session) {
      session.active = false;
      return true;
    }
    return false;
  }

  getSessionCount() {
    return this.sessions.size;
  }
}

class EmojiAwareCursor {
  getVisualPosition(text, codeUnitOffset) {
    let visualPos = 0;
    for (let i = 0; i < codeUnitOffset && i < text.length; i++) {
      const code = text.charCodeAt(i);
      if (code >= 0xD800 && code <= 0xDBFF) {
        i++;
      }
      visualPos++;
    }
    return visualPos;
  }

  getCodeUnitOffset(text, visualPosition) {
    let codeUnitOffset = 0;
    let visualPos = 0;
    while (visualPos < visualPosition && codeUnitOffset < text.length) {
      const code = text.charCodeAt(codeUnitOffset);
      codeUnitOffset++;
      if (code >= 0xD800 && code <= 0xDBFF) {
        codeUnitOffset++;
      }
      visualPos++;
    }
    return codeUnitOffset;
  }

  getTextLength(text) {
    let length = 0;
    for (let i = 0; i < text.length; i++) {
      const code = text.charCodeAt(i);
      if (code >= 0xD800 && code <= 0xDBFF) {
        i++;
      }
      length++;
    }
    return length;
  }

  insertAt(text, visualPosition, content) {
    const offset = this.getCodeUnitOffset(text, visualPosition);
    return text.slice(0, offset) + content + text.slice(offset);
  }

  deleteAt(text, visualPosition, count) {
    const startOffset = this.getCodeUnitOffset(text, visualPosition);
    const endOffset = this.getCodeUnitOffset(text, visualPosition + count);
    return text.slice(0, startOffset) + text.slice(endOffset);
  }
}

class SplitBrainDetector {
  constructor(expectedNodes) {
    this.expectedNodes = expectedNodes;
    this.partitions = [];
  }

  detectSplit(visibleNodes) {
    const visibleSet = new Set(visibleNodes);
    const invisibleNodes = this.expectedNodes.filter(n => !visibleSet.has(n));

    if (invisibleNodes.length === 0) {
      return { hasSplit: false, partitions: [visibleNodes] };
    }

    const partition1 = visibleNodes;
    const partition2 = invisibleNodes;

    const majoritySize = this.expectedNodes.length / 2;

    return {
      hasSplit: true,
      partitions: [partition1, partition2],
      hasMajority: partition1.length > majoritySize,
      canOperate: partition1.length > majoritySize,
    };
  }

  getQuorumSize() {
    return Math.floor(this.expectedNodes.length / 2) + 1;
  }

  isQuorumMet(activeNodes) {
    return activeNodes.length >= this.getQuorumSize();
  }
}

module.exports = { PresenceService, SessionManager, EmojiAwareCursor, SplitBrainDetector };

/**
 * Collaboration Features Tests
 *
 * Tests bugs D1-D10 (collaboration features)
 */

describe('PresenceService', () => {
  let PresenceService;

  beforeEach(() => {
    jest.resetModules();
    const mod = require('../../../services/presence/src/services/presence');
    PresenceService = mod.PresenceService;
  });

  describe('cursor tracking', () => {
    it('cursor tracking drift test', () => {
      const service = new PresenceService();

      service.updateCursorPosition('user1', 'doc1', 10);
      service.updateCursorPosition('user1', 'doc1', 15);

      const cursor = service.cursors.get('doc1:user1');
      expect(cursor.position).toBe(15);
    });

    it('position drift test', () => {
      const service = new PresenceService();

      for (let i = 0; i < 100; i++) {
        service.updateCursorPosition('user1', 'doc1', i);
      }

      const cursor = service.cursors.get('doc1:user1');
      expect(cursor.position).toBe(99);
    });
  });

  describe('selection highlighting', () => {
    it('selection z-index test', () => {
      const service = new PresenceService();

      const style1 = service.getSelectionStyle('user1', 'doc1');
      const style2 = service.getSelectionStyle('user2', 'doc1');

      expect(style1.zIndex).not.toBe(style2.zIndex);
    });

    it('highlight overlap test', () => {
      const service = new PresenceService();

      const style1 = service.getSelectionStyle('user1', 'doc1');
      const style2 = service.getSelectionStyle('user2', 'doc1');

      expect(style1.color).not.toBe(style2.color);
    });
  });

  describe('cursor colors', () => {
    it('cursor color collision test', () => {
      const service = new PresenceService();

      const colors = new Set();
      for (let i = 0; i < 5; i++) {
        colors.add(service.getUserColor(`user${i}`));
      }

      expect(colors.size).toBe(5);
    });

    it('color assignment test', () => {
      const service = new PresenceService();

      const color1 = service.getUserColor('user1');
      const color2 = service.getUserColor('user2');

      expect(color1).toBeDefined();
      expect(color2).toBeDefined();
    });
  });

  describe('comment anchors', () => {
    it('comment anchor invalidation test', () => {
      const service = new PresenceService();

      const anchors = service.updateCommentAnchors('doc1', {
        type: 'insert',
        position: 5,
        content: 'new text',
      });

      expect(Array.isArray(anchors)).toBe(true);
    });

    it('anchor edit test', () => {
      const service = new PresenceService();

      const anchors = service.updateCommentAnchors('doc1', {
        type: 'delete',
        position: 3,
        length: 5,
      });

      expect(Array.isArray(anchors)).toBe(true);
    });
  });

  describe('suggestion mode', () => {
    it('suggestion merge conflict test', () => {
      const service = new PresenceService();

      const content = 'Hello World';
      const suggestion = { startPos: 6, endPos: 11, newContent: 'Earth' };

      const result = service.applySuggestion('doc1', suggestion, content);
      expect(result).toBe('Hello Earth');
    });

    it('suggest mode test', () => {
      const service = new PresenceService();

      const content = 'abcdef';
      const suggestion = { startPos: 2, endPos: 4, newContent: 'XY' };

      const result = service.applySuggestion('doc1', suggestion, content);
      expect(result).toBe('abXYef');
    });
  });

  describe('track changes', () => {
    it('track changes attribution test', () => {
      const service = new PresenceService();

      const change = service.trackChange('doc1', 'user1', { type: 'insert', position: 0, content: 'Hello' });

      expect(change.userId).toBe('user1');
    });

    it('attribution test', () => {
      const service = new PresenceService();

      const change1 = service.trackChange('doc1', 'user1', { type: 'insert' });
      const change2 = service.trackChange('doc1', 'user2', { type: 'delete' });

      expect(change1.userId).toBe('user1');
      expect(change2.userId).toBe('user2');
    });
  });

  describe('collaborative undo', () => {
    it('collaborative undo scope test', () => {
      const { UndoRedoManager } = require('../../../shared/realtime');
      const manager = new UndoRedoManager();

      manager.pushOperation('user1', { type: 'insert', position: 0, content: 'A' });
      manager.pushOperation('user2', { type: 'insert', position: 1, content: 'B' });

      const undone = manager.undo('user1');
      expect(undone).toBeDefined();
    });

    it('undo scope test', () => {
      const { UndoRedoManager } = require('../../../shared/realtime');
      const manager = new UndoRedoManager();

      manager.pushOperation('user1', { type: 'insert', position: 0, content: 'X' });
      manager.pushOperation('user2', { type: 'insert', position: 1, content: 'Y' });

      const undone = manager.undo('user1');
      expect(undone.type).toBe('delete');
    });
  });

  describe('notification ordering', () => {
    it('realtime notification ordering test', () => {
      const service = new PresenceService();

      service.queueNotification({ type: 'edit', timestamp: 1, seq: 1 });
      service.queueNotification({ type: 'comment', timestamp: 2, seq: 2 });
      service.queueNotification({ type: 'join', timestamp: 3, seq: 3 });

      const notifications = service.getNotifications(0);
      expect(notifications).toHaveLength(3);

      for (let i = 1; i < notifications.length; i++) {
        expect(notifications[i].seq).toBeGreaterThan(notifications[i - 1].seq);
      }
    });

    it('notification order test', () => {
      const service = new PresenceService();

      for (let i = 0; i < 10; i++) {
        service.queueNotification({ type: 'test', timestamp: i + 1, seq: i + 1 });
      }

      const notifications = service.getNotifications(0);
      expect(notifications).toHaveLength(10);
    });
  });

  describe('presence timeout', () => {
    it('presence indicator timeout test', async () => {
      const service = new PresenceService();

      service.cursors.set('doc1:user1', {
        userId: 'user1',
        documentId: 'doc1',
        position: 5,
        timestamp: Date.now() - 120000,
      });

      const presence = await service.getPresence('doc1');

      const staleEntries = presence.filter(p => Date.now() - p.timestamp > 60000);
      expect(staleEntries).toHaveLength(0);
    });

    it('stale presence test', async () => {
      const service = new PresenceService();

      service.cursors.set('doc1:user1', {
        userId: 'user1',
        documentId: 'doc1',
        position: 5,
        timestamp: Date.now() - 300000,
      });

      const presence = await service.getPresence('doc1');
      const activePresence = presence.filter(p => Date.now() - p.timestamp < 60000);
      expect(activePresence).toHaveLength(0);
    });
  });

  describe('selection z-index uniqueness', () => {
    it('each user should get a unique z-index for selection overlay', () => {
      const service = new PresenceService();
      const zIndices = new Set();
      for (let i = 0; i < 5; i++) {
        const style = service.getSelectionStyle(`user${i}`, 'doc1');
        zIndices.add(style.zIndex);
      }
      // All 5 users should have different z-index values
      expect(zIndices.size).toBe(5);
    });

    it('z-index should vary by user to prevent visual overlap', () => {
      const service = new PresenceService();
      const z1 = service.getSelectionStyle('alice', 'doc1').zIndex;
      const z2 = service.getSelectionStyle('bob', 'doc1').zIndex;
      const z3 = service.getSelectionStyle('carol', 'doc1').zIndex;
      // At least two of three should differ
      const unique = new Set([z1, z2, z3]);
      expect(unique.size).toBeGreaterThan(1);
    });

    it('same user should get consistent z-index across calls', () => {
      const service = new PresenceService();
      const z1 = service.getSelectionStyle('user1', 'doc1').zIndex;
      const z2 = service.getSelectionStyle('user1', 'doc1').zIndex;
      expect(z1).toBe(z2);
    });

    it('z-index should differentiate at least 10 concurrent users', () => {
      const service = new PresenceService();
      const zSet = new Set();
      for (let i = 0; i < 10; i++) {
        zSet.add(service.getSelectionStyle(`u${i}`, 'doc1').zIndex);
      }
      expect(zSet.size).toBe(10);
    });
  });

  describe('comment anchor updates', () => {
    it('updateCommentAnchors should return adjusted anchors for insert operations', () => {
      const service = new PresenceService();
      const result = service.updateCommentAnchors('doc1', {
        type: 'insert',
        position: 5,
        content: 'inserted text',
      });
      // Should return updated anchor positions, not empty array
      // BUG: always returns empty array regardless of operation
      expect(result).not.toEqual([]);
    });

    it('updateCommentAnchors should handle delete operations', () => {
      const service = new PresenceService();
      const result = service.updateCommentAnchors('doc1', {
        type: 'delete',
        position: 3,
        length: 5,
      });
      // Should process the operation and return meaningful result
      expect(Array.isArray(result)).toBe(true);
      // A non-trivial implementation would process operations
      expect(result.length).toBeGreaterThanOrEqual(0);
    });

    it('updateCommentAnchors should not always return empty for valid input', () => {
      const service = new PresenceService();
      // Set up some state first
      service.updateCursorPosition('user1', 'doc1', 10);
      const result = service.updateCommentAnchors('doc1', {
        type: 'insert',
        position: 0,
        content: 'prefix ',
      });
      // Should return the adjusted anchors
      // BUG: returns [] unconditionally
      expect(result).toBeDefined();
      // The result should not be hardcoded empty
      if (typeof result === 'object' && !Array.isArray(result)) {
        expect(Object.keys(result).length).toBeGreaterThan(0);
      }
    });

    it('comment anchors should shift when text is inserted before them', () => {
      const service = new PresenceService();
      const anchors = service.updateCommentAnchors('doc1', {
        type: 'insert',
        position: 0,
        content: 'new text ',
      });
      // Real implementation should return shifted anchors
      // BUG: always returns [] so anchors are never updated
      expect(anchors).not.toEqual([]);
    });

    it('updateCommentAnchors result should reflect the operation applied', () => {
      const service = new PresenceService();
      const r1 = service.updateCommentAnchors('doc1', { type: 'insert', position: 0, content: 'a' });
      const r2 = service.updateCommentAnchors('doc1', { type: 'delete', position: 0, length: 1 });
      // Different operations should produce different results
      // BUG: both return [] regardless
      const bothEmpty = (r1.length === 0) && (r2.length === 0);
      expect(bothEmpty).toBe(false);
    });
  });

  describe('trackChange attribution', () => {
    it('trackChange should always use provided userId, not internal state', () => {
      const service = new PresenceService();
      service.currentUser = 'admin';
      const change = service.trackChange('doc1', 'contributor', { type: 'insert' });
      // BUG: uses this.currentUser || userId, so if currentUser is set, it overrides
      expect(change.userId).toBe('contributor');
    });

    it('trackChange should not be affected by currentUser property', () => {
      const service = new PresenceService();
      service.currentUser = 'system';
      const c1 = service.trackChange('doc1', 'user-a', { type: 'insert' });
      const c2 = service.trackChange('doc1', 'user-b', { type: 'delete' });
      expect(c1.userId).toBe('user-a');
      expect(c2.userId).toBe('user-b');
    });

    it('trackChange userId parameter should take precedence over this.currentUser', () => {
      const service = new PresenceService();
      service.currentUser = 'override-user';
      const change = service.trackChange('doc1', 'actual-user', { type: 'format' });
      expect(change.userId).not.toBe('override-user');
      expect(change.userId).toBe('actual-user');
    });

    it('multiple users tracked changes should have correct attribution', () => {
      const service = new PresenceService();
      service.currentUser = 'background-user';
      const changes = [];
      for (let i = 0; i < 5; i++) {
        changes.push(service.trackChange('doc1', `editor-${i}`, { type: 'edit' }));
      }
      for (let i = 0; i < 5; i++) {
        expect(changes[i].userId).toBe(`editor-${i}`);
      }
    });
  });

  describe('collaborative locks', () => {
    it('lock escalation deadlock test', async () => {
      const service = new PresenceService();

      await service.acquireCollaborativeLock('user1', 'doc1', 'section-a');
      await service.acquireCollaborativeLock('user2', 'doc1', 'section-b');

      await expect(
        service.acquireCollaborativeLock('user1', 'doc1', 'section-b')
      ).rejects.toThrow();
    });

    it('lock deadlock test', async () => {
      const service = new PresenceService();

      await service.acquireCollaborativeLock('user1', 'doc1', 'header');

      await expect(
        Promise.race([
          service.acquireCollaborativeLock('user2', 'doc1', 'header'),
          new Promise((_, reject) => setTimeout(() => reject(new Error('timeout')), 5000)),
        ])
      ).rejects.toThrow();
    });
  });
});

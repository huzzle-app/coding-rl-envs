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

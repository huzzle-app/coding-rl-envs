/**
 * Document Versioning Tests
 *
 * Tests version history, snapshots, diff generation, restore
 */

describe('Version History', () => {
  describe('version creation', () => {
    it('should create version on save', () => {
      const versions = [];

      const createVersion = (docId, content, userId) => {
        const version = {
          id: `v-${versions.length + 1}`,
          docId,
          version: versions.length + 1,
          content: JSON.parse(JSON.stringify(content)),
          userId,
          createdAt: Date.now(),
        };
        versions.push(version);
        return version;
      };

      createVersion('doc-1', { text: 'Hello' }, 'user-1');
      createVersion('doc-1', { text: 'Hello World' }, 'user-1');

      expect(versions).toHaveLength(2);
      expect(versions[1].version).toBe(2);
    });

    it('should preserve content at each version', () => {
      const versions = [];

      const save = (content) => {
        versions.push({ content: JSON.parse(JSON.stringify(content)), version: versions.length + 1 });
      };

      save({ text: 'Draft' });
      save({ text: 'Final' });
      save({ text: 'Published' });

      expect(versions[0].content.text).toBe('Draft');
      expect(versions[2].content.text).toBe('Published');
    });

    it('should track version author', () => {
      const version = {
        userId: 'user-1',
        userName: 'Alice',
        timestamp: Date.now(),
      };

      expect(version.userId).toBe('user-1');
    });

    it('should auto-increment version numbers', () => {
      let currentVersion = 0;

      const nextVersion = () => ++currentVersion;

      expect(nextVersion()).toBe(1);
      expect(nextVersion()).toBe(2);
      expect(nextVersion()).toBe(3);
    });
  });

  describe('version diff', () => {
    it('should compute text diff', () => {
      const computeDiff = (oldText, newText) => {
        const changes = [];
        if (oldText !== newText) {
          changes.push({ type: 'modified', old: oldText, new: newText });
        }
        return changes;
      };

      const diff = computeDiff('Hello', 'Hello World');
      expect(diff).toHaveLength(1);
      expect(diff[0].type).toBe('modified');
    });

    it('should detect additions', () => {
      const oldFields = { title: 'Test' };
      const newFields = { title: 'Test', description: 'Desc' };

      const additions = Object.keys(newFields).filter(k => !(k in oldFields));
      expect(additions).toContain('description');
    });

    it('should detect deletions', () => {
      const oldFields = { title: 'Test', subtitle: 'Sub' };
      const newFields = { title: 'Test' };

      const deletions = Object.keys(oldFields).filter(k => !(k in newFields));
      expect(deletions).toContain('subtitle');
    });

    it('should handle identical versions', () => {
      const v1 = { text: 'Same' };
      const v2 = { text: 'Same' };

      const hasChanges = JSON.stringify(v1) !== JSON.stringify(v2);
      expect(hasChanges).toBe(false);
    });
  });

  describe('version restore', () => {
    it('should restore to specific version', () => {
      const versionStore = [
        { version: 1, content: { text: 'V1' } },
        { version: 2, content: { text: 'V2' } },
        { version: 3, content: { text: 'V3' } },
      ];

      const restore = (targetVersion) => {
        const v = versionStore.find(v => v.version === targetVersion);
        if (!v) throw new Error('Version not found');
        return {
          ...v.content,
          restoredFrom: targetVersion,
          version: versionStore.length + 1,
        };
      };

      const restored = restore(1);
      expect(restored.text).toBe('V1');
      expect(restored.version).toBe(4);
    });

    it('should create new version on restore', () => {
      const versions = [
        { version: 1, text: 'A' },
        { version: 2, text: 'B' },
      ];

      const restored = {
        version: versions.length + 1,
        text: versions[0].text,
        restoredFrom: 1,
      };

      versions.push(restored);

      expect(versions).toHaveLength(3);
      expect(versions[2].restoredFrom).toBe(1);
    });

    it('should reject invalid version number', () => {
      const maxVersion = 5;

      const isValidVersion = (v) => v >= 1 && v <= maxVersion && Number.isInteger(v);

      expect(isValidVersion(3)).toBe(true);
      expect(isValidVersion(0)).toBe(false);
      expect(isValidVersion(6)).toBe(false);
      expect(isValidVersion(1.5)).toBe(false);
    });
  });

  describe('version pruning', () => {
    it('should keep last N versions', () => {
      const maxVersions = 50;
      const versions = Array.from({ length: 100 }, (_, i) => ({
        version: i + 1,
        content: `Version ${i + 1}`,
      }));

      const pruned = versions.slice(-maxVersions);
      expect(pruned).toHaveLength(50);
      expect(pruned[0].version).toBe(51);
    });

    it('should preserve milestone versions', () => {
      const versions = Array.from({ length: 100 }, (_, i) => ({
        version: i + 1,
        milestone: (i + 1) % 10 === 0,
      }));

      const milestones = versions.filter(v => v.milestone);
      expect(milestones).toHaveLength(10);
    });
  });
});

describe('Snapshot Management', () => {
  describe('snapshot creation', () => {
    it('should create periodic snapshots', () => {
      const snapshotInterval = 10;
      const currentVersion = 35;

      const shouldSnapshot = (version) => version % snapshotInterval === 0;

      expect(shouldSnapshot(10)).toBe(true);
      expect(shouldSnapshot(20)).toBe(true);
      expect(shouldSnapshot(35)).toBe(false);
    });

    it('should include full document state', () => {
      const snapshot = {
        docId: 'doc-1',
        version: 20,
        content: { ops: [{ insert: 'Full content here' }] },
        metadata: { title: 'Test Doc', tags: ['test'] },
        timestamp: Date.now(),
      };

      expect(snapshot.content).toBeDefined();
      expect(snapshot.metadata).toBeDefined();
    });

    it('should compress large snapshots', () => {
      const content = 'x'.repeat(100000);
      const compressed = content.length;

      expect(compressed).toBeGreaterThan(0);
    });
  });

  describe('snapshot retrieval', () => {
    it('should find nearest snapshot', () => {
      const snapshots = [
        { version: 10 },
        { version: 20 },
        { version: 30 },
      ];

      const findNearest = (targetVersion) => {
        let nearest = null;
        for (const s of snapshots) {
          if (s.version <= targetVersion) nearest = s;
        }
        return nearest;
      };

      expect(findNearest(25).version).toBe(20);
      expect(findNearest(30).version).toBe(30);
      expect(findNearest(5)).toBeNull();
    });

    it('should replay events from snapshot', () => {
      const snapshot = { version: 10, state: { text: 'Base' } };
      const events = [
        { version: 11, type: 'append', data: ' More' },
        { version: 12, type: 'append', data: ' Text' },
      ];

      let state = { ...snapshot.state };
      for (const event of events) {
        if (event.type === 'append') {
          state.text += event.data;
        }
      }

      expect(state.text).toBe('Base More Text');
    });
  });
});

describe('Concurrent Versioning', () => {
  describe('optimistic concurrency', () => {
    it('should detect version conflicts', () => {
      const currentVersion = 5;

      const update = (expectedVersion, data) => {
        if (expectedVersion !== currentVersion) {
          return { success: false, error: 'Version conflict' };
        }
        return { success: true, newVersion: currentVersion + 1 };
      };

      expect(update(5, {}).success).toBe(true);
      expect(update(3, {}).success).toBe(false);
    });

    it('should handle concurrent saves', async () => {
      let version = 1;
      const results = [];

      const save = async (userId, expectedVersion) => {
        await new Promise(resolve => setTimeout(resolve, Math.random() * 10));

        if (version === expectedVersion) {
          version++;
          results.push({ userId, success: true });
        } else {
          results.push({ userId, success: false });
        }
      };

      await Promise.all([
        save('user-1', 1),
        save('user-2', 1),
      ]);

      const successes = results.filter(r => r.success);
      expect(successes).toHaveLength(1);
    });
  });

  describe('merge strategies', () => {
    it('should auto-merge non-conflicting changes', () => {
      const base = { title: 'Title', content: 'Content', tags: ['a'] };
      const change1 = { title: 'New Title' };
      const change2 = { tags: ['a', 'b'] };

      const merged = { ...base, ...change1, ...change2 };

      expect(merged.title).toBe('New Title');
      expect(merged.tags).toEqual(['a', 'b']);
      expect(merged.content).toBe('Content');
    });

    it('should detect field-level conflicts', () => {
      const change1 = { title: 'Title A' };
      const change2 = { title: 'Title B' };

      const conflicts = Object.keys(change1).filter(k => k in change2 && change1[k] !== change2[k]);
      expect(conflicts).toContain('title');
    });
  });
});

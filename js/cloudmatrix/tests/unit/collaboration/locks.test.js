/**
 * Collaborative Locking Tests
 *
 * Tests section locks, lock escalation, deadlock detection, lock timeout
 */

describe('Section Locking', () => {
  describe('lock acquisition', () => {
    it('should acquire section lock', () => {
      const locks = new Map();

      const acquire = (userId, docId, section) => {
        const key = `${docId}:${section}`;
        if (locks.has(key) && locks.get(key).userId !== userId) return false;
        locks.set(key, { userId, acquiredAt: Date.now() });
        return true;
      };

      expect(acquire('user-1', 'doc-1', 'header')).toBe(true);
      expect(locks.size).toBe(1);
    });

    it('should prevent conflicting locks', () => {
      const locks = new Map();

      const acquire = (userId, docId, section) => {
        const key = `${docId}:${section}`;
        if (locks.has(key) && locks.get(key).userId !== userId) return false;
        locks.set(key, { userId });
        return true;
      };

      acquire('user-1', 'doc-1', 'intro');
      const result = acquire('user-2', 'doc-1', 'intro');

      expect(result).toBe(false);
    });

    it('should allow same user to re-acquire', () => {
      const locks = new Map();

      const acquire = (userId, docId, section) => {
        const key = `${docId}:${section}`;
        if (locks.has(key) && locks.get(key).userId !== userId) return false;
        locks.set(key, { userId });
        return true;
      };

      acquire('user-1', 'doc-1', 'header');
      expect(acquire('user-1', 'doc-1', 'header')).toBe(true);
    });

    it('should allow locks on different sections', () => {
      const locks = new Map();

      const acquire = (userId, docId, section) => {
        const key = `${docId}:${section}`;
        if (locks.has(key) && locks.get(key).userId !== userId) return false;
        locks.set(key, { userId });
        return true;
      };

      expect(acquire('user-1', 'doc-1', 'header')).toBe(true);
      expect(acquire('user-2', 'doc-1', 'body')).toBe(true);
    });

    it('should isolate locks across documents', () => {
      const locks = new Map();

      const acquire = (userId, docId, section) => {
        const key = `${docId}:${section}`;
        if (locks.has(key) && locks.get(key).userId !== userId) return false;
        locks.set(key, { userId });
        return true;
      };

      expect(acquire('user-1', 'doc-1', 'header')).toBe(true);
      expect(acquire('user-2', 'doc-2', 'header')).toBe(true);
    });
  });

  describe('lock release', () => {
    it('should release owned lock', () => {
      const locks = new Map();

      const acquire = (userId, key) => {
        locks.set(key, { userId });
      };

      const release = (userId, key) => {
        const lock = locks.get(key);
        if (lock && lock.userId === userId) {
          locks.delete(key);
          return true;
        }
        return false;
      };

      acquire('user-1', 'doc-1:header');
      expect(release('user-1', 'doc-1:header')).toBe(true);
      expect(locks.size).toBe(0);
    });

    it('should not release lock owned by another', () => {
      const locks = new Map();
      locks.set('doc-1:header', { userId: 'user-1' });

      const release = (userId, key) => {
        const lock = locks.get(key);
        if (lock && lock.userId === userId) {
          locks.delete(key);
          return true;
        }
        return false;
      };

      expect(release('user-2', 'doc-1:header')).toBe(false);
      expect(locks.size).toBe(1);
    });

    it('should release all user locks on disconnect', () => {
      const locks = new Map();
      locks.set('doc-1:header', { userId: 'user-1' });
      locks.set('doc-1:body', { userId: 'user-1' });
      locks.set('doc-1:footer', { userId: 'user-2' });

      const releaseAll = (userId) => {
        for (const [key, lock] of locks) {
          if (lock.userId === userId) locks.delete(key);
        }
      };

      releaseAll('user-1');
      expect(locks.size).toBe(1);
    });
  });
});

describe('Lock Timeout', () => {
  describe('auto-expiry', () => {
    it('should expire stale locks', () => {
      const locks = new Map();
      const lockTimeout = 30000;

      locks.set('doc-1:header', { userId: 'user-1', acquiredAt: Date.now() - 60000 });
      locks.set('doc-1:body', { userId: 'user-2', acquiredAt: Date.now() });

      const cleanupStaleLocks = () => {
        const now = Date.now();
        for (const [key, lock] of locks) {
          if (now - lock.acquiredAt > lockTimeout) {
            locks.delete(key);
          }
        }
      };

      cleanupStaleLocks();
      expect(locks.size).toBe(1);
    });

    it('should refresh lock on heartbeat', () => {
      const locks = new Map();

      locks.set('doc-1:header', { userId: 'user-1', acquiredAt: Date.now() - 25000 });

      const refresh = (key, userId) => {
        const lock = locks.get(key);
        if (lock && lock.userId === userId) {
          lock.acquiredAt = Date.now();
          return true;
        }
        return false;
      };

      expect(refresh('doc-1:header', 'user-1')).toBe(true);

      const lock = locks.get('doc-1:header');
      expect(Date.now() - lock.acquiredAt).toBeLessThan(1000);
    });
  });
});

describe('Deadlock Detection', () => {
  describe('wait-for graph', () => {
    it('should detect simple deadlock', () => {
      const waitGraph = new Map();

      waitGraph.set('user-1', 'resource-b');
      waitGraph.set('user-2', 'resource-a');

      const holders = new Map();
      holders.set('resource-a', 'user-1');
      holders.set('resource-b', 'user-2');

      const detectDeadlock = () => {
        for (const [user, waitingFor] of waitGraph) {
          const holder = holders.get(waitingFor);
          if (holder && waitGraph.has(holder)) {
            const holderWaitsFor = waitGraph.get(holder);
            const holderBlockedBy = holders.get(holderWaitsFor);
            if (holderBlockedBy === user) return true;
          }
        }
        return false;
      };

      expect(detectDeadlock()).toBe(true);
    });

    it('should not flag non-deadlock waits', () => {
      const waitGraph = new Map();
      waitGraph.set('user-1', 'resource-a');

      const holders = new Map();
      holders.set('resource-a', 'user-2');

      const hasDeadlock = () => {
        for (const [user, waitingFor] of waitGraph) {
          const holder = holders.get(waitingFor);
          if (holder && waitGraph.has(holder)) return true;
        }
        return false;
      };

      expect(hasDeadlock()).toBe(false);
    });
  });

  describe('deadlock resolution', () => {
    it('should abort lower priority request', () => {
      const priorities = { 'user-1': 10, 'user-2': 5 };

      const resolveDeadlock = (user1, user2) => {
        return priorities[user1] > priorities[user2] ? user2 : user1;
      };

      const victim = resolveDeadlock('user-1', 'user-2');
      expect(victim).toBe('user-2');
    });

    it('should use timestamp for priority', () => {
      const requests = [
        { userId: 'user-1', timestamp: 1000 },
        { userId: 'user-2', timestamp: 500 },
      ];

      const older = requests.reduce((a, b) => a.timestamp < b.timestamp ? a : b);
      expect(older.userId).toBe('user-2');
    });
  });
});

describe('Lock Escalation', () => {
  describe('section to document lock', () => {
    it('should escalate when all sections locked', () => {
      const sections = ['header', 'body', 'footer'];
      const locks = new Map();

      for (const s of sections) {
        locks.set(`doc-1:${s}`, { userId: 'user-1' });
      }

      const allLocked = sections.every(s => {
        const lock = locks.get(`doc-1:${s}`);
        return lock && lock.userId === 'user-1';
      });

      expect(allLocked).toBe(true);
    });

    it('should not escalate with mixed owners', () => {
      const sections = ['header', 'body', 'footer'];
      const locks = new Map();

      locks.set('doc-1:header', { userId: 'user-1' });
      locks.set('doc-1:body', { userId: 'user-2' });

      const sameOwner = sections.every(s => {
        const lock = locks.get(`doc-1:${s}`);
        return lock && lock.userId === 'user-1';
      });

      expect(sameOwner).toBe(false);
    });
  });

  describe('lock downgrade', () => {
    it('should downgrade document lock to section', () => {
      const docLock = { docId: 'doc-1', userId: 'user-1', type: 'document' };

      const downgrade = (lock, section) => {
        return {
          ...lock,
          type: 'section',
          section,
        };
      };

      const sectionLock = downgrade(docLock, 'header');
      expect(sectionLock.type).toBe('section');
      expect(sectionLock.section).toBe('header');
    });
  });
});

describe('Lock Queue', () => {
  describe('waitlist management', () => {
    it('should queue waiting requests', () => {
      const waitQueue = [];

      const enqueue = (userId, resource) => {
        waitQueue.push({ userId, resource, enqueuedAt: Date.now() });
      };

      enqueue('user-2', 'doc-1:header');
      enqueue('user-3', 'doc-1:header');

      expect(waitQueue).toHaveLength(2);
    });

    it('should grant lock to first waiter', () => {
      const waitQueue = [
        { userId: 'user-2', enqueuedAt: 1000 },
        { userId: 'user-3', enqueuedAt: 2000 },
      ];

      const next = waitQueue.shift();
      expect(next.userId).toBe('user-2');
    });

    it('should remove user from queue on cancel', () => {
      const queue = ['user-2', 'user-3', 'user-4'];

      const cancel = (userId) => {
        const idx = queue.indexOf(userId);
        if (idx >= 0) queue.splice(idx, 1);
      };

      cancel('user-3');
      expect(queue).toEqual(['user-2', 'user-4']);
    });

    it('should timeout queued requests', () => {
      const queue = [
        { userId: 'user-2', enqueuedAt: Date.now() - 60000 },
        { userId: 'user-3', enqueuedAt: Date.now() },
      ];

      const timeout = 30000;
      const active = queue.filter(q => Date.now() - q.enqueuedAt < timeout);

      expect(active).toHaveLength(1);
      expect(active[0].userId).toBe('user-3');
    });
  });
});

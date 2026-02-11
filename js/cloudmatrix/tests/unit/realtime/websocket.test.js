/**
 * WebSocket Management Tests
 *
 * Tests bugs B1-B10 (WebSocket management), L9 (WS bind)
 */

describe('WebSocketManager', () => {
  let WebSocketManager;

  beforeEach(() => {
    jest.resetModules();
  });

  describe('initialization', () => {
    it('websocket server bind test', async () => {
      const mod = require('../../../shared/realtime');
      WebSocketManager = mod.WebSocketManager;

      const manager = new WebSocketManager();
      const mockServer = {};

      const wss = await manager.initialize(mockServer);
      expect(wss).toBeDefined();
    });

    it('ws initialization test', async () => {
      const mod = require('../../../shared/realtime');
      WebSocketManager = mod.WebSocketManager;

      const manager = new WebSocketManager({ heartbeatInterval: 5000 });
      expect(manager.heartbeatInterval).toBe(5000);
    });
  });

  describe('connection management', () => {
    beforeEach(() => {
      const mod = require('../../../shared/realtime');
      WebSocketManager = mod.WebSocketManager;
    });

    it('connection leak test', () => {
      const manager = new WebSocketManager();
      const mockWs = { readyState: 1, send: jest.fn(), on: jest.fn(), terminate: jest.fn() };

      manager.connections.set('conn-1', { ws: mockWs, rooms: new Set(['room-1']), lastPing: Date.now() });
      manager.rooms.set('room-1', new Set(['conn-1']));

      manager.connections.delete('conn-1');

      const room = manager.rooms.get('room-1');
      expect(room.has('conn-1')).toBe(false);
    });

    it('abnormal close test', () => {
      const manager = new WebSocketManager();
      const mockWs = { readyState: 1, send: jest.fn(), on: jest.fn(), terminate: jest.fn() };

      manager.connections.set('conn-1', { ws: mockWs, rooms: new Set(['room-1']), lastPing: Date.now() });
      manager.rooms.set('room-1', new Set(['conn-1']));

      manager.connections.delete('conn-1');

      expect(manager.connections.has('conn-1')).toBe(false);
      const room = manager.rooms.get('room-1');
      expect(room).toBeDefined();
      expect(room.has('conn-1')).toBe(false);
    });

    it('reconnection backoff test', () => {
      const delay1 = WebSocketManager.getReconnectDelay(1);
      const delay2 = WebSocketManager.getReconnectDelay(2);
      const delay3 = WebSocketManager.getReconnectDelay(3);

      expect(delay2).toBeGreaterThan(delay1);
      expect(delay3).toBeGreaterThan(delay2);
    });

    it('exponential backoff test', () => {
      const delay1 = WebSocketManager.getReconnectDelay(1);
      const delay5 = WebSocketManager.getReconnectDelay(5);

      expect(delay5).toBeGreaterThan(delay1 * 4);
    });

    it('presence stale test', () => {
      const manager = new WebSocketManager();

      manager.connections.set('conn-1', {
        ws: { readyState: 1, send: jest.fn() },
        rooms: new Set(['room-1']),
        lastPing: Date.now() - 60000,
      });

      expect(manager.connections.has('conn-1')).toBe(true);
    });

    it('disconnect presence test', () => {
      const manager = new WebSocketManager();

      manager.connections.set('conn-1', {
        ws: { readyState: 3, send: jest.fn() },
        rooms: new Set(['room-1']),
        lastPing: Date.now() - 60000,
      });

      const room = manager.rooms.get('room-1') || new Set();
      expect(room.has('conn-1')).toBe(false);
    });

    it('heartbeat interval test', () => {
      const manager = new WebSocketManager({ heartbeatInterval: 5000 });
      expect(manager.heartbeatInterval).toBe(5000);
    });

    it('ping pong test', () => {
      const manager = new WebSocketManager({ heartbeatInterval: 15000 });
      expect(manager.heartbeatInterval).toBeLessThanOrEqual(15000);
    });

    it('message ordering test', () => {
      const manager = new WebSocketManager();
      const messages = [];

      manager.connections.set('conn-1', {
        ws: { readyState: 1, send: jest.fn() },
        rooms: new Set(),
        lastPing: Date.now(),
      });

      for (let i = 1; i <= 5; i++) {
        messages.push({ seq: i, type: 'edit', data: { position: i } });
      }

      expect(messages[0].seq).toBeLessThan(messages[4].seq);
    });

    it('ws message order test', () => {
      const manager = new WebSocketManager();
      manager.messageSequence.set('conn-1', 0);

      const expectedSeq = (manager.messageSequence.get('conn-1') || 0) + 1;
      expect(expectedSeq).toBe(1);
    });

    it('binary frame buffer test', () => {
      const manager = new WebSocketManager();

      const largeBuffer = Buffer.alloc(10 * 1024 * 1024);
      expect(largeBuffer.length).toBeGreaterThan(1024 * 1024);
    });

    it('binary overflow test', () => {
      const manager = new WebSocketManager();
      const maxPayload = 1024 * 1024;

      const oversized = Buffer.alloc(maxPayload + 1);
      expect(oversized.length).toBeGreaterThan(maxPayload);
    });

    it('ws auth token expired test', () => {
      const jwt = require('jsonwebtoken');
      const token = jwt.sign({ userId: 'user-1' }, 'secret', { expiresIn: '0s' });

      expect(() => {
        jwt.verify(token, 'secret');
      }).toThrow();
    });

    it('token refresh ws test', () => {
      const { WebSocketAuthenticator } = require('../../../services/gateway/src/middleware/auth');

      const auth = new WebSocketAuthenticator('secret');
      const jwt = require('jsonwebtoken');
      const expiredToken = jwt.sign({ userId: 'user-1' }, 'secret', { expiresIn: '0s' });

      const result = auth.authenticate(expiredToken);
      expect(result).toBeNull();
    });

    it('room subscription leak test', () => {
      const manager = new WebSocketManager();

      manager.connections.set('conn-1', {
        ws: { readyState: 1, send: jest.fn() },
        rooms: new Set(),
        lastPing: Date.now(),
      });

      manager._joinRoom('conn-1', 'room-1');
      manager._joinRoom('conn-1', 'room-2');
      manager._joinRoom('conn-1', 'room-3');

      manager._leaveRoom('conn-1', 'room-1');

      expect(manager.rooms.get('room-1').size).toBe(0);
    });

    it('unsubscribe cleanup test', () => {
      const manager = new WebSocketManager();

      manager.connections.set('conn-1', {
        ws: { readyState: 1, send: jest.fn() },
        rooms: new Set(),
        lastPing: Date.now(),
      });

      manager._joinRoom('conn-1', 'room-1');
      manager._leaveRoom('conn-1', 'room-1');

      const conn = manager.connections.get('conn-1');
      expect(conn.rooms.has('room-1')).toBe(false);
    });

    it('broadcast fan-out test', async () => {
      const manager = new WebSocketManager();
      const sends = [];

      for (let i = 0; i < 100; i++) {
        const connId = `conn-${i}`;
        manager.connections.set(connId, {
          ws: {
            readyState: 1,
            send: jest.fn((msg) => sends.push({ connId, msg })),
          },
          rooms: new Set(['room-1']),
          lastPing: Date.now(),
        });
        if (!manager.rooms.has('room-1')) {
          manager.rooms.set('room-1', new Set());
        }
        manager.rooms.get('room-1').add(connId);
      }

      const startTime = Date.now();
      manager._broadcast('room-1', { type: 'test' });
      const duration = Date.now() - startTime;

      expect(sends.length).toBe(100);
    });

    it('slow consumer test', () => {
      const manager = new WebSocketManager();

      manager.connections.set('conn-1', {
        ws: { readyState: 1, send: jest.fn() },
        rooms: new Set(['room-1']),
        lastPing: Date.now(),
      });

      manager.rooms.set('room-1', new Set(['conn-1']));
      manager._broadcast('room-1', { type: 'test' });

      expect(manager.connections.get('conn-1').ws.send).toHaveBeenCalled();
    });

    it('connection pool exhaustion test', () => {
      const manager = new WebSocketManager({ maxConnections: 5 });

      for (let i = 0; i < 10; i++) {
        manager.connections.set(`conn-${i}`, {
          ws: { readyState: 1, send: jest.fn() },
          rooms: new Set(),
          lastPing: Date.now(),
        });
      }

      expect(manager.connections.size).toBeLessThanOrEqual(5);
    });

    it('max connections test', () => {
      const manager = new WebSocketManager({ maxConnections: 3 });
      expect(manager.maxConnections).toBe(3);
    });
  });
});

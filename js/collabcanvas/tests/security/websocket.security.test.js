/**
 * WebSocket Security Tests
 *
 * Tests WebSocket authentication and authorization using actual source services.
 * Tests bugs D1 (JWT secret validation), D4 (timing), A4 (stale closure)
 */

// Set JWT_SECRET before requiring JwtService so the config module picks it up
process.env.JWT_SECRET = 'test-secret-key-that-is-long-enough-for-signing';
const JwtService = require('../../src/services/auth/jwt.service');
const BroadcastService = require('../../src/services/collaboration/broadcast.service');
const PresenceService = require('../../src/services/collaboration/presence.service');

describe('WebSocket Security', () => {
  let originalEnv;

  beforeEach(() => {
    originalEnv = { ...process.env };
    process.env.JWT_SECRET = 'test-secret-key-that-is-long-enough-for-signing';
  });

  afterEach(() => {
    process.env = originalEnv;
    jest.clearAllMocks();
  });

  describe('connection authentication', () => {
    it('should generate valid token for socket auth', () => {
      const jwtService = new JwtService();

      const payload = { userId: 'user-1', socketId: 'socket-123' };
      const token = jwtService.generateToken(payload, { expiresIn: '1h' });

      expect(token).toBeDefined();
      expect(typeof token).toBe('string');

      const decoded = jwtService.verifyToken(token);
      expect(decoded.userId).toBe('user-1');
    });

    it('should reject connection with expired token', async () => {
      const jwtService = new JwtService();

      const payload = { userId: 'user-1' };
      const token = jwtService.generateToken(payload, { expiresIn: '1ms' });

      // Wait for expiry
      await new Promise(r => setTimeout(r, 50));

      // BUG D1: verifyToken returns null instead of throwing on expired tokens
      // When fixed, this should throw an error
      expect(() => jwtService.verifyToken(token)).toThrow();
    });

    it('should reject tampered socket auth tokens', () => {
      const jwtService = new JwtService();

      const token = jwtService.generateToken({ userId: 'user-1' });
      const parts = token.split('.');
      parts[1] = Buffer.from(JSON.stringify({ userId: 'hacked' })).toString('base64url');
      const tamperedToken = parts.join('.');

      // BUG D1: verifyToken returns null instead of throwing
      expect(() => jwtService.verifyToken(tamperedToken)).toThrow();
    });

    it('should not accept tokens signed with wrong secret', () => {
      const jwtService = new JwtService();
      const token = jwtService.generateToken({ userId: 'user-1' });

      process.env.JWT_SECRET = 'different-secret-key-32-chars-long!!';
      const otherService = new JwtService();

      // BUG D1: verifyToken returns null instead of throwing
      expect(() => otherService.verifyToken(token)).toThrow();
    });
  });

  describe('message validation', () => {
    it('should validate broadcast message format via BroadcastService', async () => {
      const mockIo = {
        to: jest.fn().mockReturnThis(),
        emit: jest.fn(),
      };
      const mockRedis = {
        publish: jest.fn().mockResolvedValue(1),
      };

      const broadcastService = new BroadcastService(mockIo, mockRedis);

      await broadcastService.broadcastToBoard('board-1', 'element:update', {
        elementId: 'elem-1',
        changes: { x: 100 },
      });

      expect(mockIo.to).toHaveBeenCalledWith('board:board-1');
      expect(mockIo.emit).toHaveBeenCalledWith('element:update', expect.objectContaining({
        elementId: 'elem-1',
      }));
    });

    it('should limit broadcast to correct room only', async () => {
      const mockIo = {
        to: jest.fn().mockReturnThis(),
        except: jest.fn().mockReturnThis(),
        emit: jest.fn(),
      };
      const mockRedis = {
        publish: jest.fn().mockResolvedValue(1),
      };

      const broadcastService = new BroadcastService(mockIo, mockRedis);

      await broadcastService.broadcastToBoard('board-1', 'update', { data: 'test' }, 'socket-exclude');

      // Should target the correct room
      expect(mockIo.to).toHaveBeenCalledWith('board:board-1');
      // Should not broadcast to unrelated rooms
      expect(mockIo.to).not.toHaveBeenCalledWith('board:board-2');
    });
  });

  describe('presence security', () => {
    it('should track user presence via PresenceService', async () => {
      const mockRedis = {
        hset: jest.fn().mockResolvedValue(1),
        hdel: jest.fn().mockResolvedValue(1),
        hgetall: jest.fn().mockResolvedValue({}),
        expire: jest.fn().mockResolvedValue(1),
      };

      const presenceService = new PresenceService(mockRedis);
      const mockSocket = { id: 'socket-1', on: jest.fn(), off: jest.fn() };
      const user = { id: 'user-1', firstName: 'Test', lastName: 'User' };

      const presence = await presenceService.trackUser(mockSocket, 'board-1', user);

      expect(mockRedis.hset).toHaveBeenCalledWith(
        'presence:board-1',
        'user-1',
        expect.any(String)
      );
    });

    it('should clean up presence on disconnect', async () => {
      const mockRedis = {
        hset: jest.fn().mockResolvedValue(1),
        hdel: jest.fn().mockResolvedValue(1),
        hgetall: jest.fn().mockResolvedValue({}),
        expire: jest.fn().mockResolvedValue(1),
      };

      const presenceService = new PresenceService(mockRedis);
      const mockSocket = { id: 'socket-1', on: jest.fn(), off: jest.fn() };
      const user = { id: 'user-1', firstName: 'Test', lastName: 'User' };

      await presenceService.trackUser(mockSocket, 'board-1', user);
      await presenceService.removeUser(mockSocket, 'board-1', 'user-1');

      expect(mockRedis.hdel).toHaveBeenCalledWith('presence:board-1', 'user-1');
    });

    /**
     * BUG A3: Heartbeat listener not removed on disconnect — memory leak
     */
    it('should remove heartbeat listener on user removal', async () => {
      const mockRedis = {
        hset: jest.fn().mockResolvedValue(1),
        hdel: jest.fn().mockResolvedValue(1),
        hgetall: jest.fn().mockResolvedValue({}),
        expire: jest.fn().mockResolvedValue(1),
      };

      const presenceService = new PresenceService(mockRedis);
      const mockSocket = { id: 'socket-1', on: jest.fn(), off: jest.fn() };
      const user = { id: 'user-1', firstName: 'Test', lastName: 'User' };

      await presenceService.trackUser(mockSocket, 'board-1', user);
      await presenceService.removeUser(mockSocket, 'board-1', 'user-1');

      // BUG A3: socket.off('heartbeat', ...) is never called
      expect(mockSocket.off).toHaveBeenCalledWith('heartbeat', expect.any(Function));
    });
  });

  describe('rate limiting and DoS protection', () => {
    it('should handle rapid cursor updates without crashing', async () => {
      const mockRedis = {
        hset: jest.fn().mockResolvedValue(1),
        hgetall: jest.fn().mockResolvedValue({}),
        expire: jest.fn().mockResolvedValue(1),
      };

      const presenceService = new PresenceService(mockRedis);
      const mockSocket = { id: 'socket-1', on: jest.fn(), off: jest.fn() };
      const user = { id: 'user-1', firstName: 'Test', lastName: 'User' };

      await presenceService.trackUser(mockSocket, 'board-1', user);

      // Rapid cursor updates should not crash
      const updates = [];
      for (let i = 0; i < 100; i++) {
        updates.push(presenceService.updateCursor('board-1', 'user-1', { x: i, y: i }));
      }

      await expect(Promise.all(updates)).resolves.toBeDefined();
    });

    it('should handle concurrent user tracking', async () => {
      const mockRedis = {
        hset: jest.fn().mockResolvedValue(1),
        hdel: jest.fn().mockResolvedValue(1),
        hgetall: jest.fn().mockResolvedValue({}),
        expire: jest.fn().mockResolvedValue(1),
      };

      const presenceService = new PresenceService(mockRedis);

      // Track 10 users concurrently
      const promises = Array(10).fill(null).map((_, i) => {
        const socket = { id: `socket-${i}`, on: jest.fn(), off: jest.fn() };
        const user = { id: `user-${i}`, firstName: `User`, lastName: `${i}` };
        return presenceService.trackUser(socket, 'board-1', user);
      });

      await Promise.all(promises);

      expect(presenceService.getUserCount('board-1')).toBe(10);
    });
  });
});

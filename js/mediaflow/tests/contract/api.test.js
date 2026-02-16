/**
 * API Contract Tests
 *
 * Tests service API contracts using actual source modules.
 * Exercises bugs K1 (feature flags), K3 (rate limit string),
 * E1 (JWT claims), F1 (bitrate precision).
 */

const config = require('../../services/gateway/src/config');
const { BitrateCalculator } = require('../../services/transcode/src/services/bitrate');

describe('Gateway API Contract', () => {
  describe('Video Endpoints', () => {
    it('should have feature flags as booleans not undefined', () => {
      // BUG K1: Feature flags are process.env values (undefined when not set)
      // They should default to false, not undefined
      expect(typeof config.featureFlags.enableHDR).toBe('boolean');
    });

    it('should have enable4K as boolean', () => {
      // BUG K1: process.env.FEATURE_4K is undefined when not set
      expect(typeof config.featureFlags.enable4K).toBe('boolean');
    });

    it('should have enableLiveStreaming as boolean', () => {
      // BUG K1: process.env.FEATURE_LIVE is undefined when not set
      expect(typeof config.featureFlags.enableLiveStreaming).toBe('boolean');
    });

    it('should have rate limit max as number', () => {
      // BUG K3: process.env values are strings, max is '100' not 100
      expect(typeof config.rateLimit.max).toBe('number');
    });

    it('should have rate limit window as number', () => {
      expect(typeof config.rateLimit.windowMs).toBe('number');
      expect(config.rateLimit.windowMs).toBe(60000);
    });
  });

  describe('Auth Endpoints', () => {
    it('should not use wildcard CORS origin', () => {
      // Security: CORS origin should not default to '*'
      expect(config.cors.origin).not.toBe('*');
    });

    it('should have credentials enabled for CORS', () => {
      expect(config.cors.credentials).toBe(true);
    });

    it('should have service URLs configured', () => {
      expect(config.services.auth.url).toBeDefined();
      expect(config.services.users.url).toBeDefined();
      expect(config.services.upload.url).toBeDefined();
      expect(config.services.catalog.url).toBeDefined();
    });
  });

  describe('User Endpoints', () => {
    it('should have all 9 service entries', () => {
      const serviceNames = Object.keys(config.services);
      expect(serviceNames).toHaveLength(9);
      expect(serviceNames).toContain('auth');
      expect(serviceNames).toContain('streaming');
      expect(serviceNames).toContain('billing');
    });

    it('should have service name matching key', () => {
      for (const [key, service] of Object.entries(config.services)) {
        expect(service.name).toBe(key);
      }
    });
  });
});

describe('Internal Service Contracts', () => {
  describe('Transcode Service', () => {
    it('should return integer bitrate values', () => {
      const calc = new BitrateCalculator();
      const bitrate = calc.calculate(1920, 1080, 30);

      expect(Number.isInteger(bitrate)).toBe(true);
    });

    it('should return adaptive tiers with required fields', () => {
      const calc = new BitrateCalculator();
      const tiers = calc.calculateAdaptiveTiers(1920, 1080, 30);

      for (const tier of tiers) {
        expect(tier).toHaveProperty('width');
        expect(tier).toHaveProperty('height');
        expect(tier).toHaveProperty('bitrate');
        expect(tier).toHaveProperty('label');
        expect(typeof tier.width).toBe('number');
        expect(typeof tier.bitrate).toBe('number');
      }
    });
  });

  describe('Event Contracts', () => {
    it('should have consul configuration', () => {
      expect(config.consul).toBeDefined();
      expect(config.consul.host).toBeDefined();
      expect(config.consul.port).toBeDefined();
    });
  });
});

describe('Error Response Contracts', () => {
  it('should have default port configured', () => {
    // Port should be from env or default 3000
    expect(config.port).toBeDefined();
  });

  it('should not have JWT secret as undefined in production', () => {
    // BUG K2: jwtSecret comes from env and could be undefined
    // Should have validation or a secure default
    expect(config.jwtSecret).toBeDefined();
  });

  it('should have consul port as number', () => {
    const port = parseInt(config.consul.port, 10);
    expect(port).toBe(8500);
  });
});

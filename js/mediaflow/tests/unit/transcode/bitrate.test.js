/**
 * Bitrate Calculator Unit Tests
 *
 * Tests bugs F1 (float precision), F3 (motion factor), F4 (VBV overflow)
 */

describe('BitrateCalculator', () => {
  let BitrateCalculator;

  beforeEach(() => {
    jest.resetModules();
    const bitrate = require('../../../services/transcode/src/services/bitrate');
    BitrateCalculator = bitrate.BitrateCalculator;
  });

  describe('basic calculation', () => {
    it('should calculate bitrate for standard resolutions', () => {
      const calculator = new BitrateCalculator();

      const bitrate1080 = calculator.calculate(1920, 1080, 30, 'h264');
      const bitrate720 = calculator.calculate(1280, 720, 30, 'h264');

      expect(bitrate1080).toBeGreaterThan(bitrate720);
      expect(typeof bitrate1080).toBe('number');
    });

    it('should apply codec efficiency factor', () => {
      const calculator = new BitrateCalculator();

      const h264 = calculator.calculate(1920, 1080, 30, 'h264');
      const h265 = calculator.calculate(1920, 1080, 30, 'h265');

      // H.265 should be ~30% more efficient
      expect(h265).toBeLessThan(h264);
    });
  });

  describe('precision', () => {
    
    it('bitrate precision test', () => {
      const calculator = new BitrateCalculator();

      // Calculate for known values
      // 1920 * 1080 * 0.1 * 1.0 * 1.0 = 207360 exactly
      const bitrate = calculator.calculate(1920, 1080, 24, 'h264');

      // Should be exactly 207360, not 207359.99999999997
      expect(Number.isInteger(bitrate)).toBe(true);
    });

    it('float calculation test', () => {
      const calculator = new BitrateCalculator();

      // Multiple calculations should be consistent
      const results = [];
      for (let i = 0; i < 10; i++) {
        results.push(calculator.calculate(1920, 1080, 30, 'h264'));
      }

      // All results should be identical
      const unique = [...new Set(results)];
      expect(unique.length).toBe(1);
    });
  });

  describe('adaptive tiers', () => {
    
    it('motion factor test', () => {
      const calculator = new BitrateCalculator();

      const lowMotion = calculator.calculateAdaptiveTiers(1920, 1080, 30, {
        motionFactor: 0.8,
      });

      const highMotion = calculator.calculateAdaptiveTiers(1920, 1080, 30, {
        motionFactor: 1.5,
      });

      // High motion should require higher bitrate
      
      expect(highMotion[0].bitrate).toBeGreaterThan(lowMotion[0].bitrate * 1.5);
    });

    it('adaptive bitrate test', () => {
      const calculator = new BitrateCalculator();

      const tiers = calculator.calculateAdaptiveTiers(1920, 1080, 30);

      // Should have 4 tiers
      expect(tiers.length).toBe(4);

      // Tiers should be in descending bitrate order
      for (let i = 1; i < tiers.length; i++) {
        expect(tiers[i].bitrate).toBeLessThan(tiers[i - 1].bitrate);
      }
    });
  });

  describe('VBV buffer', () => {
    it('should calculate buffer size', () => {
      const calculator = new BitrateCalculator();

      const buffer = calculator.calculateVBVBuffer(5000, 2);

      expect(buffer).toBeGreaterThan(0);
      expect(Number.isInteger(buffer)).toBe(true);
    });

    
    it('should handle high bitrates without overflow', () => {
      const calculator = new BitrateCalculator();

      // 4K at 50Mbps
      const buffer = calculator.calculateVBVBuffer(50000, 2);

      // Should not overflow
      expect(buffer).toBeGreaterThan(0);
      expect(buffer).toBeLessThan(Number.MAX_SAFE_INTEGER);
    });
  });
});

describe('HDRMetadata', () => {
  let HDRMetadata;

  beforeEach(() => {
    jest.resetModules();
    const bitrate = require('../../../services/transcode/src/services/bitrate');
    HDRMetadata = bitrate.HDRMetadata;
  });

  describe('parsing', () => {
    it('should parse HDR metadata', () => {
      const hdr = new HDRMetadata();

      hdr.parse({
        maxCLL: 1000,
        maxFALL: 400,
        masteringDisplay: {
          redX: 0.708,
          redY: 0.292,
          greenX: 0.170,
          greenY: 0.797,
          blueX: 0.131,
          blueY: 0.046,
          whiteX: 0.3127,
          whiteY: 0.3290,
          minLuminance: 0.0001,
          maxLuminance: 1000,
        },
      });

      expect(hdr.maxCLL).toBe(1000);
      expect(hdr.masteringDisplay).toBeDefined();
    });
  });

  describe('validation', () => {
    
    it('should validate HDR ranges', () => {
      const hdr = new HDRMetadata();

      // Invalid maxCLL (too high)
      hdr.parse({ maxCLL: 20000, maxFALL: 400 });

      // Should fail validation
      expect(hdr.validate()).toBe(false);
    });

    it('should accept valid HDR metadata', () => {
      const hdr = new HDRMetadata();

      hdr.parse({ maxCLL: 1000, maxFALL: 400 });

      expect(hdr.validate()).toBe(true);
    });
  });
});

/**
 * Throughput Performance Tests
 *
 * Tests BitrateCalculator computation correctness and performance.
 * Exercises bugs F1 (Math.floor vs Math.round), F3 (motion factor added not multiplied),
 * F4 (VBV buffer overflow).
 */

const { BitrateCalculator, HDRMetadata } = require('../../services/transcode/src/services/bitrate');

describe('API Throughput', () => {
  let calc;

  beforeEach(() => {
    calc = new BitrateCalculator();
  });

  describe('Read Operations', () => {
    it('should calculate correct bitrate for 1080p30', () => {
      const bitrate = calc.calculate(1920, 1080, 30);

      // 1920*1080*0.1 = 207360 base
      // frameRateMultiplier = 1 + (30-24)*0.02 = 1.12
      // 207360 * 1.12 = 232083.2
      // BUG F1: Math.floor gives 232083, Math.round would give 232083
      // For this case both give same, but edge cases differ
      expect(bitrate).toBeGreaterThan(0);
      expect(typeof bitrate).toBe('number');
    });

    it('should use Math.round for bitrate precision', () => {
      // Use specific dimensions that produce a .5 fractional result
      // 1280*720*0.1 = 92160
      // frameRate=60: multiplier = 1 + (60-24)*0.02 = 1.72
      // 92160 * 1.72 = 158515.2
      // Math.floor = 158515, Math.round = 158515
      // Try h265 codec: 158515.2 * 0.7 = 110960.64
      // Math.floor = 110960, Math.round = 110961
      const bitrate = calc.calculate(1280, 720, 60, 'h265');

      // BUG F1: Math.floor truncates, should Math.round for proper precision
      // 1280*720*0.1 * (1+(60-24)*0.02) * 0.7 = 110960.64
      expect(bitrate).toBe(Math.round(1280 * 720 * 0.1 * (1 + (60 - 24) * 0.02) * 0.7));
    });

    it('should handle h265 codec efficiency', () => {
      const h264 = calc.calculate(1920, 1080, 24);
      const h265 = calc.calculate(1920, 1080, 24, 'h265');

      // h265 should be 70% of h264
      expect(h265).toBeLessThan(h264);
      expect(h265 / h264).toBeCloseTo(0.7, 1);
    });

    it('should handle av1 codec efficiency', () => {
      const h264 = calc.calculate(1920, 1080, 24);
      const av1 = calc.calculate(1920, 1080, 24, 'av1');

      // av1 should be 60% of h264
      expect(av1 / h264).toBeCloseTo(0.6, 1);
    });
  });

  describe('Write Operations', () => {
    it('should calculate adaptive tiers with correct motion factor', () => {
      const tiers = calc.calculateAdaptiveTiers(1920, 1080, 30, { motionFactor: 1.5 });

      // BUG F3: motionFactor is ADDED instead of MULTIPLIED
      // With multiplication: each tier's bitrate *= 1.5
      // With addition: each tier's bitrate += 1.5 (negligible change)
      expect(tiers).toHaveLength(4);

      const baseBitrate = calc.calculate(1920, 1080, 30);
      const topTier = tiers[0];

      // Top tier should be base * motionFactor = base * 1.5
      expect(topTier.bitrate).toBeCloseTo(baseBitrate * 1.5, -1);
    });

    it('should produce decreasing bitrates across tiers', () => {
      const tiers = calc.calculateAdaptiveTiers(1920, 1080, 30);

      for (let i = 1; i < tiers.length; i++) {
        expect(tiers[i].bitrate).toBeLessThan(tiers[i - 1].bitrate);
      }
    });

    it('should label tiers correctly', () => {
      const tiers = calc.calculateAdaptiveTiers(1920, 1080, 30);

      expect(tiers[0].label).toBe('1080p');
      expect(tiers[1].label).toBe('810p');
      expect(tiers[2].label).toBe('540p');
      expect(tiers[3].label).toBe('270p');
    });

    it('should scale tier dimensions correctly', () => {
      const tiers = calc.calculateAdaptiveTiers(1920, 1080, 30);

      expect(tiers[0].width).toBe(1920);
      expect(tiers[0].height).toBe(1080);
      expect(tiers[1].width).toBe(1440);
      expect(tiers[1].height).toBe(810);
    });
  });

  describe('Mixed Workload', () => {
    it('should apply motion factor multiplicatively', () => {
      const noMotion = calc.calculateAdaptiveTiers(1920, 1080, 30, { motionFactor: 1.0 });
      const highMotion = calc.calculateAdaptiveTiers(1920, 1080, 30, { motionFactor: 2.0 });

      // BUG F3: With addition, difference is only 1.0 per tier
      // With multiplication, high motion should be 2x no motion
      const ratio = highMotion[0].bitrate / noMotion[0].bitrate;
      expect(ratio).toBeCloseTo(2.0, 1);
    });
  });
});

describe('Database Throughput', () => {
  let calc;

  beforeEach(() => {
    calc = new BitrateCalculator();
  });

  describe('Query Performance', () => {
    it('should calculate VBV buffer correctly for 1080p', () => {
      const bitrate = calc.calculate(1920, 1080, 30); // ~232083
      const buffer = calc.calculateVBVBuffer(bitrate, 2);

      // buffer = bitrate * 1000 * 2 / 8 = bitrate * 250
      const expected = Math.round(bitrate * 1000 * 2 / 8);
      expect(buffer).toBe(expected);
    });

    it('should calculate VBV buffer for 4K without overflow', () => {
      // BUG F4: 4K bitrate can cause overflow in intermediate calculation
      const bitrate = calc.calculate(3840, 2160, 60);
      const buffer = calc.calculateVBVBuffer(bitrate, 2);

      // Should be a reasonable positive number, not negative (overflow)
      expect(buffer).toBeGreaterThan(0);
      // For 4K60: ~1.5M bitrate, buffer should be ~375MB
      expect(buffer).toBeLessThan(1e10);
    });

    it('should handle very high bitrate VBV calculation', () => {
      // Extreme case: 50000 kbps (50 Mbps)
      const buffer = calc.calculateVBVBuffer(50000, 3);

      // 50000 * 1000 * 3 / 8 = 18,750,000
      expect(buffer).toBe(Math.round(50000 * 1000 * 3 / 8));
    });
  });

  describe('Connection Pool', () => {
    it('should handle frame rate below 24fps', () => {
      const bitrate = calc.calculate(1920, 1080, 15);

      // frameRateMultiplier = 1 + (15-24)*0.02 = 1 - 0.18 = 0.82
      // Lower frame rate should produce lower bitrate
      const bitrate24 = calc.calculate(1920, 1080, 24);
      expect(bitrate).toBeLessThan(bitrate24);
    });

    it('should handle unknown codec gracefully', () => {
      const bitrate = calc.calculate(1920, 1080, 30, 'unknown-codec');

      // Should fall back to factor 1.0
      const h264 = calc.calculate(1920, 1080, 30, 'h264');
      expect(bitrate).toBe(h264);
    });
  });
});

describe('Cache Throughput', () => {
  describe('Hit Rate', () => {
    it('should parse HDR metadata correctly', () => {
      const hdr = new HDRMetadata();
      hdr.parse({
        maxCLL: 1000,
        maxFALL: 400,
        masteringDisplay: {
          redX: 0.68, redY: 0.32,
          greenX: 0.265, greenY: 0.69,
          blueX: 0.15, blueY: 0.06,
          whiteX: 0.3127, whiteY: 0.3290,
          minLuminance: 0.0001,
          maxLuminance: 1000,
        },
      });

      expect(hdr.maxCLL).toBe(1000);
      expect(hdr.maxFALL).toBe(400);
      expect(hdr.masteringDisplay.redX).toBe(0.68);
    });

    it('should validate HDR metadata range', () => {
      const hdr = new HDRMetadata();

      // maxCLL of 20000 exceeds valid range (0-10000)
      hdr.parse({ maxCLL: 20000, maxFALL: 5000 });

      // BUG: Only checks maxCLL < 0, doesn't check upper bound
      const valid = hdr.validate();
      expect(valid).toBe(false);
    });
  });

  describe('Cache Operations', () => {
    it('should reject negative maxCLL', () => {
      const hdr = new HDRMetadata();
      hdr.parse({ maxCLL: -100, maxFALL: 400 });

      expect(hdr.validate()).toBe(false);
    });
  });
});

describe('Message Queue Throughput', () => {
  let calc;

  beforeEach(() => {
    calc = new BitrateCalculator();
  });

  describe('Publish Rate', () => {
    it('should calculate vp9 codec efficiency', () => {
      const h264 = calc.calculate(1920, 1080, 30);
      const vp9 = calc.calculate(1920, 1080, 30, 'vp9');

      expect(vp9 / h264).toBeCloseTo(0.75, 1);
    });
  });

  describe('Consume Rate', () => {
    it('should produce integer bitrate values', () => {
      const bitrate = calc.calculate(1280, 720, 30);
      expect(Number.isInteger(bitrate)).toBe(true);
    });

    it('should handle 480p calculation', () => {
      const bitrate = calc.calculate(854, 480, 30);
      expect(bitrate).toBeGreaterThan(0);
      expect(bitrate).toBeLessThan(100000);
    });
  });
});

describe('Streaming Throughput', () => {
  describe('Video Delivery', () => {
    it('should handle custom pixelsPerBit', () => {
      const calc = new BitrateCalculator({ pixelsPerBit: 0.2 });
      const bitrate = calc.calculate(1920, 1080, 24);

      const defaultCalc = new BitrateCalculator();
      const defaultBitrate = defaultCalc.calculate(1920, 1080, 24);

      expect(bitrate).toBeCloseTo(defaultBitrate * 2, -1);
    });

    it('should calculate 4K bitrate', () => {
      const calc = new BitrateCalculator();
      const bitrate4K = calc.calculate(3840, 2160, 30);
      const bitrate1080 = calc.calculate(1920, 1080, 30);

      // 4K has 4x pixels of 1080p
      expect(bitrate4K / bitrate1080).toBeCloseTo(4, 0);
    });
  });
});

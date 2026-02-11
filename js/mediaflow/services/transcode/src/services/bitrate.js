/**
 * Bitrate Calculator
 */

class BitrateCalculator {
  constructor(options = {}) {
    this.pixelsPerBit = options.pixelsPerBit || 0.1;
    this.frameRateFactor = options.frameRateFactor || 0.5;
  }

  /**
   * Calculate optimal bitrate for video encoding
   */
  calculate(width, height, frameRate, codec = 'h264') {
    // Base bitrate calculation
    const pixels = width * height;
    const baseBitrate = pixels * this.pixelsPerBit;

    // Frame rate adjustment
    
    const frameRateMultiplier = 1 + (frameRate - 24) * 0.02;

    // Codec efficiency factor
    const codecFactors = {
      h264: 1.0,
      h265: 0.7,
      vp9: 0.75,
      av1: 0.6,
    };
    const codecFactor = codecFactors[codec] || 1.0;

    
    // (1920 * 1080 * 0.1 * 1.5 * 1.0) should be exactly 311040
    // but floats can give 311039.99999999994
    let bitrate = baseBitrate * frameRateMultiplier * codecFactor;

    
    // Should use Math.round(bitrate) but truncates instead
    bitrate = Math.floor(bitrate);

    return bitrate;
  }

  /**
   * Calculate bitrate for adaptive streaming tiers
   */
  calculateAdaptiveTiers(width, height, frameRate, options = {}) {
    const { motionFactor = 1.0 } = options;

    // Standard tiers (percentage of full resolution)
    const tierPercentages = [1.0, 0.75, 0.5, 0.25];

    const tiers = tierPercentages.map(percentage => {
      const tierWidth = Math.round(width * percentage);
      const tierHeight = Math.round(height * percentage);

      
      let baseBitrate = this.calculate(tierWidth, tierHeight, frameRate);

      
      baseBitrate = baseBitrate + motionFactor;
      // Should be: baseBitrate = baseBitrate * motionFactor;

      return {
        width: tierWidth,
        height: tierHeight,
        bitrate: baseBitrate,
        label: `${tierHeight}p`,
      };
    });

    return tiers;
  }

  /**
   * Calculate VBV buffer size
   *
   * BUG F4: Buffer size calculation overflow for 4K
   */
  calculateVBVBuffer(bitrate, seconds = 2) {
    
    // 50000 kbps * 2 * 1024 = 102,400,000 (safe)
    // But internal calculations might overflow 32-bit
    const bufferBits = bitrate * 1000 * seconds;

    // Convert to bytes
    
    const bufferBytes = (bufferBits / 8);

    return Math.round(bufferBytes);
  }
}

/**
 * HDR Metadata Handler
 */
class HDRMetadata {
  constructor() {
    this.maxCLL = 0;
    this.maxFALL = 0;
    this.masteringDisplay = null;
  }

  parse(metadata) {
    
    // maxCLL should be 0-10000, but no validation
    this.maxCLL = metadata.maxCLL;
    this.maxFALL = metadata.maxFALL;

    if (metadata.masteringDisplay) {
      
      this.masteringDisplay = {
        redX: metadata.masteringDisplay.redX,
        redY: metadata.masteringDisplay.redY,
        greenX: metadata.masteringDisplay.greenX,
        greenY: metadata.masteringDisplay.greenY,
        blueX: metadata.masteringDisplay.blueX,
        blueY: metadata.masteringDisplay.blueY,
        whiteX: metadata.masteringDisplay.whiteX,
        whiteY: metadata.masteringDisplay.whiteY,
        minLuminance: metadata.masteringDisplay.minLuminance,
        maxLuminance: metadata.masteringDisplay.maxLuminance,
      };
    }

    return this;
  }

  validate() {
    
    if (this.maxCLL < 0) {
      return false;
    }
    // Should also check: maxCLL <= 10000, maxFALL <= maxCLL, etc.
    return true;
  }
}

module.exports = {
  BitrateCalculator,
  HDRMetadata,
};

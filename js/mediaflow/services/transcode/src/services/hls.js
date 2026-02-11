/**
 * HLS Generator
 *
 * BUG F2: Segment duration inconsistency
 * BUG F6: Discontinuity handling errors
 */

class HLSGenerator {
  constructor(options = {}) {
    this.targetDuration = options.targetDuration || 6;
    this.playlistType = options.playlistType || 'vod';
  }

  /**
   * Generate master playlist
   */
  async generateMaster(videoId, variants) {
    let playlist = '#EXTM3U\n';
    playlist += '#EXT-X-VERSION:3\n';

    for (const variant of variants) {
      const bandwidth = variant.bitrate * 1000; // kbps to bps
      const resolution = `${variant.width}x${variant.height}`;

      playlist += `#EXT-X-STREAM-INF:BANDWIDTH=${bandwidth},RESOLUTION=${resolution}\n`;
      playlist += `${videoId}/${variant.label}/playlist.m3u8\n`;
    }

    return playlist;
  }

  /**
   * Generate media playlist
   *
   * BUG F2: Segment durations don't match target
   */
  async generate(videoId, variant, segments) {
    let playlist = '#EXTM3U\n';
    playlist += '#EXT-X-VERSION:3\n';
    playlist += `#EXT-X-TARGETDURATION:${this.targetDuration}\n`;
    playlist += '#EXT-X-MEDIA-SEQUENCE:0\n';

    if (this.playlistType === 'vod') {
      playlist += '#EXT-X-PLAYLIST-TYPE:VOD\n';
    }

    
    // Target is 6 seconds but actual segments might be 4-8 seconds
    for (let i = 0; i < segments.length; i++) {
      const segment = segments[i];

      
      // This violates HLS spec if duration > target + 0.5
      playlist += `#EXTINF:${segment.duration.toFixed(3)},\n`;

      
      if (segment.discontinuity) {
        
        playlist += '#EXT-X-DISCONTINUITY\n';
      }

      playlist += `segment${i}.ts\n`;
    }

    if (this.playlistType === 'vod') {
      playlist += '#EXT-X-ENDLIST\n';
    }

    return playlist;
  }

  /**
   * Calculate optimal segment boundaries
   *
   * BUG F7: Keyframe alignment issues
   */
  calculateSegments(duration, keyframes) {
    const segments = [];
    let currentStart = 0;

    
    // This causes playback issues on segment boundaries
    while (currentStart < duration) {
      let segmentEnd = currentStart + this.targetDuration;

      if (segmentEnd > duration) {
        segmentEnd = duration;
      }

      
      // const nearestKeyframe = this._findNearestKeyframe(keyframes, segmentEnd);
      // segmentEnd = nearestKeyframe;

      segments.push({
        start: currentStart,
        end: segmentEnd,
        duration: segmentEnd - currentStart,
      });

      currentStart = segmentEnd;
    }

    return segments;
  }

  _findNearestKeyframe(keyframes, targetTime) {
    let nearest = keyframes[0];
    let minDiff = Math.abs(targetTime - nearest);

    for (const kf of keyframes) {
      const diff = Math.abs(targetTime - kf);
      if (diff < minDiff) {
        minDiff = diff;
        nearest = kf;
      }
    }

    return nearest;
  }
}

/**
 * Live HLS Handler
 *
 * BUG F8: Live edge calculation errors
 */
class LiveHLSHandler {
  constructor(options = {}) {
    this.windowSize = options.windowSize || 3;
    this.segments = [];
    this.mediaSequence = 0;
  }

  addSegment(segment) {
    this.segments.push(segment);

    // Sliding window
    
    while (this.segments.length > this.windowSize) {
      this.segments.shift();
      this.mediaSequence++;
    }
  }

  generatePlaylist() {
    const targetDuration = Math.ceil(
      Math.max(...this.segments.map(s => s.duration))
    );

    let playlist = '#EXTM3U\n';
    playlist += '#EXT-X-VERSION:3\n';
    playlist += `#EXT-X-TARGETDURATION:${targetDuration}\n`;
    playlist += `#EXT-X-MEDIA-SEQUENCE:${this.mediaSequence}\n`;

    for (const segment of this.segments) {
      playlist += `#EXTINF:${segment.duration.toFixed(3)},\n`;
      playlist += `${segment.url}\n`;
    }

    return playlist;
  }

  /**
   * Calculate live edge position
   *
   * BUG F8: Edge position doesn't account for segment duration
   */
  calculateLiveEdge() {
    if (this.segments.length === 0) {
      return 0;
    }

    
    // Current calculation returns position too close to actual live
    const lastSegment = this.segments[this.segments.length - 1];

    
    return lastSegment.startTime + lastSegment.duration;
    // Should be: return lastSegment.startTime - (targetDuration * 3);
  }
}

module.exports = {
  HLSGenerator,
  LiveHLSHandler,
};

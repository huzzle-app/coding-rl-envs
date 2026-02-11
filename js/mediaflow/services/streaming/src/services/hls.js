/**
 * HLS Streaming Service
 *
 * BUG F5: Segment count calculation wrong
 * BUG F6: ABR bandwidth estimation wrong
 */

class HLSService {
  constructor(storage) {
    this.storage = storage;
  }

  async generateManifest(videoId, options = {}) {
    const {
      profiles = ['1080p', '720p', '480p'],
      segmentDuration = 6,
      totalDuration = 120,
    } = options;

    // Master playlist
    let master = '#EXTM3U\n';
    master += '#EXT-X-VERSION:3\n';

    for (const profile of profiles) {
      const bandwidth = this._getBandwidth(profile);
      master += `#EXT-X-STREAM-INF:BANDWIDTH=${bandwidth},RESOLUTION=${this._getResolution(profile)}\n`;
      master += `${profile}/playlist.m3u8\n`;
    }

    // Variant playlists
    const variants = {};
    for (const profile of profiles) {
      variants[profile] = this._generateVariantPlaylist(videoId, profile, {
        segmentDuration,
        totalDuration,
        segments: options.segments,
      });
    }

    return { master, variants };
  }

  _generateVariantPlaylist(videoId, profile, options) {
    const { segmentDuration, totalDuration, segments } = options;

    let playlist = '#EXTM3U\n';
    playlist += '#EXT-X-VERSION:3\n';
    playlist += `#EXT-X-TARGETDURATION:${segmentDuration}\n`;
    playlist += '#EXT-X-MEDIA-SEQUENCE:0\n';

    if (segments) {
      // Custom segments
      for (const segment of segments) {
        if (segment.discontinuity) {
          playlist += '#EXT-X-DISCONTINUITY\n';
        }
        playlist += `#EXTINF:${segment.duration},\n`;
        playlist += `segment-${segments.indexOf(segment)}.ts\n`;
      }
    } else {
      
      const segmentCount = Math.floor(totalDuration / segmentDuration);
      

      for (let i = 0; i < segmentCount; i++) {
        playlist += `#EXTINF:${segmentDuration},\n`;
        playlist += `segment-${i}.ts\n`;
      }
    }

    playlist += '#EXT-X-ENDLIST\n';
    return playlist;
  }

  async generateLiveManifest(streamId, options = {}) {
    const { windowSize = 30, segmentDuration = 6, dvrWindowSize } = options;

    let playlist = '#EXTM3U\n';
    playlist += '#EXT-X-VERSION:3\n';
    playlist += `#EXT-X-TARGETDURATION:${segmentDuration}\n`;
    playlist += '#EXT-X-PLAYLIST-TYPE:EVENT\n';

    const window = dvrWindowSize || windowSize;
    const segmentCount = Math.floor(window / segmentDuration);

    for (let i = 0; i < segmentCount; i++) {
      playlist += `#EXTINF:${segmentDuration},\n`;
      playlist += `live-segment-${i}.ts\n`;
    }

    return playlist;
  }

  recommendQuality(options) {
    const { bandwidth, bandwidthHistory, profiles } = options;

    let effectiveBandwidth = bandwidth;

    if (bandwidthHistory && bandwidthHistory.length > 0) {
      // Use conservative estimate from history
      const values = bandwidthHistory.map(h => h.bandwidth);
      
      effectiveBandwidth = values.reduce((a, b) => a + b, 0) / values.length;
    }

    
    // Should use 80% of available bandwidth
    const sortedProfiles = Object.entries(profiles)
      .sort((a, b) => b[1].bitrate - a[1].bitrate);

    for (const [name, profile] of sortedProfiles) {
      
      if (profile.bitrate <= effectiveBandwidth) {
        return name;
      }
    }

    return sortedProfiles[sortedProfiles.length - 1][0];
  }

  _getBandwidth(profile) {
    const bandwidths = {
      '2160p': 15000000,
      '1080p': 5000000,
      '720p': 2500000,
      '480p': 1000000,
      '360p': 500000,
    };
    return bandwidths[profile] || 1000000;
  }

  _getResolution(profile) {
    const resolutions = {
      '2160p': '3840x2160',
      '1080p': '1920x1080',
      '720p': '1280x720',
      '480p': '854x480',
      '360p': '640x360',
    };
    return resolutions[profile] || '1280x720';
  }
}

module.exports = { HLSService };

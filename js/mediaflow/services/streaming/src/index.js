/**
 * MediaFlow Streaming Service
 *
 * BUG H1: Cache stampede on popular content
 * BUG H2: Hot key concentration
 * BUG H3: CDN purge race condition
 */

const express = require('express');
const { CacheManager } = require('./services/cache');
const { CDNManager } = require('./services/cdn');
const { StreamRouter } = require('./services/router');

const app = express();
app.use(express.json());

const config = {
  port: process.env.PORT || 3006,
  redis: {
    host: process.env.REDIS_HOST || 'localhost',
    port: process.env.REDIS_PORT || 6379,
  },
  cdn: {
    provider: process.env.CDN_PROVIDER || 'cloudfront',
    distributionId: process.env.CDN_DISTRIBUTION_ID,
  },
};

// Health check
app.get('/health', (req, res) => {
  res.json({ status: 'healthy', service: 'streaming' });
});

// Get video manifest
app.get('/manifest/:videoId', async (req, res) => {
  try {
    const cache = new CacheManager();
    const router = new StreamRouter();

    // Try cache first
    const cached = await cache.get(`manifest:${req.params.videoId}`);
    if (cached) {
      return res.type('application/vnd.apple.mpegurl').send(cached);
    }

    // Generate manifest
    const manifest = await router.getManifest(req.params.videoId);

    // Cache it
    await cache.set(`manifest:${req.params.videoId}`, manifest, 300);

    res.type('application/vnd.apple.mpegurl').send(manifest);
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// Get video segment
app.get('/segment/:videoId/:segment', async (req, res) => {
  try {
    const router = new StreamRouter();
    const segment = await router.getSegment(req.params.videoId, req.params.segment);

    res.type('video/MP2T').send(segment);
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// Purge cache for video
app.post('/purge/:videoId', async (req, res) => {
  try {
    const cache = new CacheManager();
    const cdn = new CDNManager(config.cdn);

    await cache.invalidate(`manifest:${req.params.videoId}`);
    await cdn.purge([`/manifest/${req.params.videoId}`, `/segment/${req.params.videoId}/*`]);

    res.json({ purged: true });
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

async function start() {
  app.listen(config.port, () => {
    console.log(`Streaming service listening on port ${config.port}`);
  });
}

start().catch(console.error);

module.exports = app;

/**
 * MediaFlow Recommendations Service
 *
 * BUG B5: Event replay doesn't maintain ordering
 * BUG B6: Projection rebuild race condition
 * BUG H2: Hot key problem in popular videos cache
 */

const express = require('express');

const app = express();
app.use(express.json());

const config = {
  port: process.env.PORT || 3007,
  cacheEnabled: process.env.CACHE_ENABLED !== 'false',
};

// In-memory storage
const userPreferences = new Map();
const videoScores = new Map();
const watchHistory = new Map();
const popularVideos = [];

// Health check
app.get('/health', (req, res) => {
  res.json({ status: 'healthy', service: 'recommendations' });
});

/**
 * Event Processor for recommendation updates
 * BUG B5: Event ordering issues
 * BUG B6: Projection rebuild race
 */
class RecommendationEventProcessor {
  constructor() {
    this.processingLock = false;
    this.eventQueue = [];
    this.projectionVersion = 0;
  }

  async processEvent(event) {
    
    // Concurrent events can corrupt projection state

    switch (event.type) {
      case 'VIDEO_WATCHED':
        await this._handleVideoWatched(event);
        break;
      case 'VIDEO_LIKED':
        await this._handleVideoLiked(event);
        break;
      case 'VIDEO_SHARED':
        await this._handleVideoShared(event);
        break;
    }

    this.projectionVersion++;
  }

  async _handleVideoWatched(event) {
    const { userId, videoId, watchDuration, totalDuration } = event.data;

    // Update watch history
    const history = watchHistory.get(userId) || [];
    history.push({
      videoId,
      watchedAt: event.timestamp,
      completionRate: watchDuration / totalDuration,
    });
    watchHistory.set(userId, history);

    // Update video popularity
    const score = videoScores.get(videoId) || { views: 0, likes: 0, shares: 0 };
    score.views++;
    videoScores.set(videoId, score);
  }

  async _handleVideoLiked(event) {
    const { videoId } = event.data;
    const score = videoScores.get(videoId) || { views: 0, likes: 0, shares: 0 };
    score.likes++;
    videoScores.set(videoId, score);
  }

  async _handleVideoShared(event) {
    const { videoId } = event.data;
    const score = videoScores.get(videoId) || { views: 0, likes: 0, shares: 0 };
    score.shares++;
    videoScores.set(videoId, score);
  }

  
  async replayEvents(events) {
    
    // Should sort by timestamp or sequence number

    for (const event of events) {
      await this.processEvent(event);
    }
  }

  
  async rebuildProjection(events) {
    
    this.projectionVersion = 0;
    userPreferences.clear();
    videoScores.clear();
    watchHistory.clear();

    
    await this.replayEvents(events);
  }
}

const eventProcessor = new RecommendationEventProcessor();

/**
 * Cache Manager with hot key issues
 * BUG H2: Single key for popular videos
 */
class RecommendationCache {
  constructor() {
    this.cache = new Map();
    this.hits = new Map();
  }

  async get(key) {
    const value = this.cache.get(key);
    if (value) {
      // Track hits
      const hits = this.hits.get(key) || 0;
      this.hits.set(key, hits + 1);
    }
    return value;
  }

  async set(key, value, ttl = 300) {
    this.cache.set(key, value);
    setTimeout(() => this.cache.delete(key), ttl * 1000);
  }

  
  async getPopularVideos() {
    
    // Under high load, this becomes a hot key bottleneck
    return this.get('popular_videos');
  }

  async setPopularVideos(videos) {
    
    return this.set('popular_videos', videos);
  }
}

const cache = new RecommendationCache();

// Get recommendations for user
app.get('/recommendations/:userId', async (req, res) => {
  try {
    const { userId } = req.params;
    const { limit = 20 } = req.query;

    // Get user watch history
    const history = watchHistory.get(userId) || [];
    const watchedIds = new Set(history.map(h => h.videoId));

    // Get all video scores
    const recommendations = [];
    for (const [videoId, score] of videoScores.entries()) {
      if (!watchedIds.has(videoId)) {
        // Simple scoring: views + likes*2 + shares*3
        const totalScore = score.views + score.likes * 2 + score.shares * 3;
        recommendations.push({ videoId, score: totalScore });
      }
    }

    // Sort by score descending
    recommendations.sort((a, b) => b.score - a.score);

    res.json({
      userId,
      recommendations: recommendations.slice(0, parseInt(limit)),
    });
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// Get popular videos

app.get('/recommendations/popular', async (req, res) => {
  try {
    const { limit = 50 } = req.query;

    
    let popular = await cache.getPopularVideos();

    if (!popular) {
      // Calculate popular videos
      const scored = [];
      for (const [videoId, score] of videoScores.entries()) {
        const totalScore = score.views + score.likes * 2 + score.shares * 3;
        scored.push({ videoId, ...score, totalScore });
      }

      scored.sort((a, b) => b.totalScore - a.totalScore);
      popular = scored.slice(0, 100);

      
      await cache.setPopularVideos(popular);
    }

    res.json({
      videos: popular.slice(0, parseInt(limit)),
    });
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// Record view event
app.post('/events/view', async (req, res) => {
  try {
    const { userId, videoId, watchDuration, totalDuration } = req.body;

    
    await eventProcessor.processEvent({
      type: 'VIDEO_WATCHED',
      timestamp: Date.now(),
      data: { userId, videoId, watchDuration, totalDuration },
    });

    res.status(202).json({ status: 'accepted' });
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// Record like event
app.post('/events/like', async (req, res) => {
  try {
    const { userId, videoId } = req.body;

    await eventProcessor.processEvent({
      type: 'VIDEO_LIKED',
      timestamp: Date.now(),
      data: { userId, videoId },
    });

    res.status(202).json({ status: 'accepted' });
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// Admin: Rebuild projection

app.post('/admin/rebuild', async (req, res) => {
  try {
    const { events } = req.body;

    
    // Should pause event processing first
    await eventProcessor.rebuildProjection(events);

    res.json({
      status: 'rebuilt',
      projectionVersion: eventProcessor.projectionVersion,
    });
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// Get similar videos
app.get('/recommendations/:videoId/similar', async (req, res) => {
  try {
    const { videoId } = req.params;
    const { limit = 10 } = req.query;

    // Simple similarity: videos watched by users who watched this one
    const similarMap = new Map();

    for (const [userId, history] of watchHistory.entries()) {
      const watchedThis = history.some(h => h.videoId === videoId);
      if (watchedThis) {
        for (const item of history) {
          if (item.videoId !== videoId) {
            const count = similarMap.get(item.videoId) || 0;
            similarMap.set(item.videoId, count + 1);
          }
        }
      }
    }

    const similar = Array.from(similarMap.entries())
      .map(([id, count]) => ({ videoId: id, similarity: count }))
      .sort((a, b) => b.similarity - a.similarity)
      .slice(0, parseInt(limit));

    res.json({ videoId, similar });
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

async function start() {
  app.listen(config.port, () => {
    console.log(`Recommendations service listening on port ${config.port}`);
  });
}

start().catch(console.error);

module.exports = { app, RecommendationEventProcessor, RecommendationCache };

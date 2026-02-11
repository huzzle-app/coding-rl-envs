/**
 * MediaFlow Analytics Service
 *
 * BUG J1: Trace context not propagated
 * BUG J3: Metric aggregation overflow
 * BUG J4: Log sampling loses errors
 * BUG D8: Cross-database query inconsistency
 */

const express = require('express');

const app = express();
app.use(express.json());

const config = {
  port: process.env.PORT || 3009,
  samplingRate: parseFloat(process.env.SAMPLING_RATE) || 0.1,
  aggregationInterval: 60000, // 1 minute
};

// In-memory storage (simulating analytics DB)
const viewEvents = [];
const aggregatedMetrics = new Map();
const userSessions = new Map();

// Health check
app.get('/health', (req, res) => {
  res.json({ status: 'healthy', service: 'analytics' });
});

/**
 * Trace Context Manager
 * BUG J1: Context not properly propagated
 */
class TraceContext {
  constructor() {
    this.spans = new Map();
  }

  startSpan(name, parentId = null) {
    const spanId = `span-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
    const span = {
      id: spanId,
      name,
      parentId,
      startTime: Date.now(),
      endTime: null,
      tags: {},
    };
    this.spans.set(spanId, span);
    return spanId;
  }

  endSpan(spanId) {
    const span = this.spans.get(spanId);
    if (span) {
      span.endTime = Date.now();
    }
  }

  
  extractFromRequest(req) {
    
    // Returns null, breaking distributed tracing
    return null;
  }

  
  injectToRequest(req, spanId) {
    
    // Does nothing, breaking trace propagation
    return req;
  }
}

const traceContext = new TraceContext();

/**
 * Metric Aggregator
 * BUG J3: Overflow on large counts
 */
class MetricAggregator {
  constructor() {
    this.counters = new Map();
    this.gauges = new Map();
    this.histograms = new Map();
  }

  incrementCounter(name, value = 1, tags = {}) {
    const key = this._makeKey(name, tags);
    const current = this.counters.get(key) || 0;

    
    // JavaScript numbers lose precision above 2^53
    this.counters.set(key, current + value);
  }

  recordHistogram(name, value, tags = {}) {
    const key = this._makeKey(name, tags);
    const bucket = this.histograms.get(key) || [];

    
    // Should use fixed-size circular buffer or sampling
    bucket.push(value);
    this.histograms.set(key, bucket);
  }

  setGauge(name, value, tags = {}) {
    const key = this._makeKey(name, tags);
    this.gauges.set(key, value);
  }

  
  aggregate() {
    const result = {
      counters: {},
      gauges: {},
      histograms: {},
    };

    for (const [key, value] of this.counters.entries()) {
      result.counters[key] = value;
    }

    for (const [key, value] of this.gauges.entries()) {
      result.gauges[key] = value;
    }

    for (const [key, values] of this.histograms.entries()) {
      
      const sum = values.reduce((a, b) => a + b, 0);
      result.histograms[key] = {
        count: values.length,
        sum,
        avg: sum / values.length,
        min: Math.min(...values),
        max: Math.max(...values),
      };
    }

    return result;
  }

  _makeKey(name, tags) {
    const tagStr = Object.entries(tags)
      .sort(([a], [b]) => a.localeCompare(b))
      .map(([k, v]) => `${k}:${v}`)
      .join(',');
    return tagStr ? `${name}{${tagStr}}` : name;
  }
}

const metrics = new MetricAggregator();

/**
 * Log Sampler
 * BUG J4: Loses important errors
 */
class LogSampler {
  constructor(samplingRate) {
    this.samplingRate = samplingRate;
  }

  shouldLog(level, message) {
    
    // Should always log errors regardless of sampling rate
    return Math.random() < this.samplingRate;
  }

  log(level, message, data = {}) {
    
    if (!this.shouldLog(level, message)) {
      return;
    }

    const entry = {
      timestamp: new Date().toISOString(),
      level,
      message,
      ...data,
    };

    // In real implementation, would send to log aggregator
    console.log(JSON.stringify(entry));
  }
}

const logger = new LogSampler(config.samplingRate);

// Record view event
app.post('/analytics/view', async (req, res) => {
  try {
    const { userId, videoId, duration, timestamp } = req.body;

    
    const traceId = traceContext.extractFromRequest(req);

    const event = {
      type: 'view',
      userId,
      videoId,
      duration,
      timestamp: timestamp || Date.now(),
      traceId, 
    };

    viewEvents.push(event);

    // Update metrics
    metrics.incrementCounter('video_views', 1, { videoId });
    metrics.recordHistogram('view_duration', duration, { videoId });

    
    logger.log('info', 'View recorded', { userId, videoId });

    res.status(202).json({ status: 'accepted' });
  } catch (error) {
    
    logger.log('error', 'Failed to record view', { error: error.message });
    res.status(500).json({ error: error.message });
  }
});

// Get video analytics

app.get('/analytics/videos/:videoId', async (req, res) => {
  try {
    const { videoId } = req.params;
    const { startDate, endDate } = req.query;

    // Filter events for this video
    let events = viewEvents.filter(e => e.videoId === videoId);

    if (startDate) {
      events = events.filter(e => e.timestamp >= new Date(startDate).getTime());
    }
    if (endDate) {
      events = events.filter(e => e.timestamp <= new Date(endDate).getTime());
    }

    
    // Video metadata comes from catalog DB
    // No transaction coordination means data can be inconsistent

    const analytics = {
      videoId,
      totalViews: events.length,
      uniqueViewers: new Set(events.map(e => e.userId)).size,
      totalWatchTime: events.reduce((sum, e) => sum + (e.duration || 0), 0),
      avgWatchTime: events.length > 0
        ? events.reduce((sum, e) => sum + (e.duration || 0), 0) / events.length
        : 0,
    };

    res.json(analytics);
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// Get user analytics
app.get('/analytics/users/:userId', async (req, res) => {
  try {
    const { userId } = req.params;

    const events = viewEvents.filter(e => e.userId === userId);

    const analytics = {
      userId,
      totalViews: events.length,
      uniqueVideos: new Set(events.map(e => e.videoId)).size,
      totalWatchTime: events.reduce((sum, e) => sum + (e.duration || 0), 0),
      recentVideos: events
        .sort((a, b) => b.timestamp - a.timestamp)
        .slice(0, 10)
        .map(e => ({ videoId: e.videoId, timestamp: e.timestamp })),
    };

    res.json(analytics);
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// Get aggregated metrics
app.get('/analytics/metrics', async (req, res) => {
  try {
    const aggregated = metrics.aggregate();
    res.json(aggregated);
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// Start user session
app.post('/analytics/sessions', async (req, res) => {
  try {
    const { userId, deviceInfo } = req.body;
    const sessionId = `session-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;

    userSessions.set(sessionId, {
      userId,
      deviceInfo,
      startTime: Date.now(),
      events: [],
    });

    metrics.incrementCounter('sessions_started');

    res.status(201).json({ sessionId });
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// Record session event
app.post('/analytics/sessions/:sessionId/events', async (req, res) => {
  try {
    const { sessionId } = req.params;
    const { type, data } = req.body;

    const session = userSessions.get(sessionId);
    if (!session) {
      return res.status(404).json({ error: 'Session not found' });
    }

    session.events.push({
      type,
      data,
      timestamp: Date.now(),
    });

    res.status(202).json({ status: 'accepted' });
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// End session
app.delete('/analytics/sessions/:sessionId', async (req, res) => {
  try {
    const { sessionId } = req.params;

    const session = userSessions.get(sessionId);
    if (!session) {
      return res.status(404).json({ error: 'Session not found' });
    }

    session.endTime = Date.now();
    const duration = session.endTime - session.startTime;

    metrics.recordHistogram('session_duration', duration);
    metrics.incrementCounter('sessions_ended');

    // Archive session data
    // In real implementation, would persist to database

    userSessions.delete(sessionId);

    res.status(204).send();
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// Real-time dashboard data
app.get('/analytics/realtime', async (req, res) => {
  try {
    const now = Date.now();
    const oneHourAgo = now - 3600000;

    const recentEvents = viewEvents.filter(e => e.timestamp >= oneHourAgo);
    const activeSessions = userSessions.size;

    res.json({
      timestamp: now,
      viewsLastHour: recentEvents.length,
      activeSessions,
      uniqueViewersLastHour: new Set(recentEvents.map(e => e.userId)).size,
    });
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

async function start() {
  app.listen(config.port, () => {
    console.log(`Analytics service listening on port ${config.port}`);
  });
}

start().catch(console.error);

module.exports = { app, TraceContext, MetricAggregator, LogSampler };

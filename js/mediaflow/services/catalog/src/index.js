/**
 * MediaFlow Catalog Service
 *
 * BUG B8: Event ordering issues
 * BUG I1: SQL injection in search
 */

const express = require('express');
const { VideoRepository } = require('./repositories/video');
const { SearchService } = require('./services/search');
const { EventStore } = require('./services/events');

const app = express();
app.use(express.json());

const config = {
  port: process.env.PORT || 3005,
};

// Health check
app.get('/health', (req, res) => {
  res.json({ status: 'healthy', service: 'catalog' });
});

// Get video by ID
app.get('/videos/:videoId', async (req, res) => {
  try {
    const repo = new VideoRepository();
    const video = await repo.findById(req.params.videoId);

    if (!video) {
      return res.status(404).json({ error: 'Video not found' });
    }

    res.json(video);
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// Search videos
app.get('/videos', async (req, res) => {
  try {
    const search = new SearchService();
    const results = await search.search(req.query);
    res.json(results);
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// Create video entry
app.post('/videos', async (req, res) => {
  try {
    const repo = new VideoRepository();
    const video = await repo.create(req.body);
    res.status(201).json(video);
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// Update video
app.put('/videos/:videoId', async (req, res) => {
  try {
    const repo = new VideoRepository();
    const video = await repo.update(req.params.videoId, req.body);
    res.json(video);
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// Event sourcing endpoints
app.get('/videos/:videoId/events', async (req, res) => {
  try {
    const store = new EventStore();
    const events = await store.getEvents(req.params.videoId);
    res.json(events);
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

async function start() {
  app.listen(config.port, () => {
    console.log(`Catalog service listening on port ${config.port}`);
  });
}

start().catch(console.error);

module.exports = app;

/**
 * MediaFlow Transcode Service
 *
 * BUG A1: Split-brain transcoding (duplicate jobs)
 * BUG F1: Bitrate calculation precision error
 * BUG F2: HLS segment duration inconsistency
 */

const express = require('express');
const { EventBus, BaseEvent } = require('@mediaflow/shared').events || require('../../../shared/events');
const { DistributedLock, LeaderElection } = require('@mediaflow/shared').utils || require('../../../shared/utils');
const { BitrateCalculator } = require('./services/bitrate');
const { HLSGenerator } = require('./services/hls');
const { TranscodeWorker } = require('./services/worker');

const app = express();
app.use(express.json());

const config = {
  port: process.env.PORT || 3004,
  redis: {
    host: process.env.REDIS_HOST || 'localhost',
    port: process.env.REDIS_PORT || 6379,
  },
  rabbitmq: {
    url: process.env.RABBITMQ_URL || 'amqp://localhost',
  },
};

// Health check
app.get('/health', (req, res) => {
  res.json({ status: 'healthy', service: 'transcode' });
});

// Get transcode job status
app.get('/jobs/:jobId', async (req, res) => {
  try {
    const job = await TranscodeWorker.getJob(req.params.jobId);
    if (!job) {
      return res.status(404).json({ error: 'Job not found' });
    }
    res.json(job);
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// Create transcode job
app.post('/jobs', async (req, res) => {
  try {
    const { videoId, sourceUrl, outputFormats } = req.body;

    const job = await TranscodeWorker.createJob({
      videoId,
      sourceUrl,
      outputFormats,
    });

    res.status(201).json(job);
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// Calculate optimal bitrate
app.post('/calculate-bitrate', (req, res) => {
  try {
    const { width, height, frameRate, codec } = req.body;

    const calculator = new BitrateCalculator();
    const bitrate = calculator.calculate(width, height, frameRate, codec);

    res.json({ bitrate, unit: 'kbps' });
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// Generate HLS manifest
app.post('/generate-hls', async (req, res) => {
  try {
    const { videoId, variants } = req.body;

    const generator = new HLSGenerator();
    const manifest = await generator.generate(videoId, variants);

    res.json(manifest);
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

async function start() {
  app.listen(config.port, () => {
    console.log(`Transcode service listening on port ${config.port}`);
  });
}

start().catch(console.error);

module.exports = app;

/**
 * MediaFlow Upload Service
 *
 * BUG D1: Saga compensation incomplete
 * BUG D2: Saga step dependencies wrong
 * BUG I4: SSRF in thumbnail fetch
 */

const express = require('express');
const multer = require('multer');
const { v4: uuidv4 } = require('uuid');

const app = express();
app.use(express.json());

const config = {
  port: process.env.PORT || 3003,
  maxFileSize: 10 * 1024 * 1024 * 1024, // 10GB
  allowedTypes: ['video/mp4', 'video/quicktime', 'video/x-msvideo', 'video/webm'],
  minioEndpoint: process.env.MINIO_ENDPOINT || 'localhost:9000',
};

const upload = multer({
  storage: multer.memoryStorage(),
  limits: { fileSize: config.maxFileSize },
});

// Health check
app.get('/health', (req, res) => {
  res.json({ status: 'healthy', service: 'upload' });
});

// Upload video
app.post('/videos', upload.single('video'), async (req, res) => {
  try {
    if (!req.file) {
      return res.status(400).json({ error: 'No video file provided' });
    }

    // Validate file type
    if (!config.allowedTypes.includes(req.file.mimetype)) {
      return res.status(400).json({ error: 'Invalid file type' });
    }

    const videoId = uuidv4();
    const saga = new UploadSaga();

    const result = await saga.execute(videoId, {
      file: req.file,
      userId: req.headers['x-user-id'],
      metadata: req.body,
    });

    res.status(201).json(result);
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// Get upload status
app.get('/videos/:videoId/status', async (req, res) => {
  try {
    // Would fetch from database
    res.json({
      videoId: req.params.videoId,
      status: 'processing',
      progress: 50,
    });
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// Fetch thumbnail from URL

app.post('/videos/:videoId/thumbnail-url', async (req, res) => {
  try {
    const { url } = req.body;

    
    // Attacker could use: url=http://169.254.169.254/latest/meta-data/
    const axios = require('axios');
    const response = await axios.get(url, {
      responseType: 'arraybuffer',
      timeout: 10000,
    });

    // Store thumbnail
    res.json({
      videoId: req.params.videoId,
      thumbnailUrl: `https://cdn.example.com/${req.params.videoId}/thumbnail.jpg`,
    });
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

/**
 * Upload Saga
 *
 * BUG D1: Compensation incomplete
 * BUG D2: Step dependencies wrong
 */
class UploadSaga {
  constructor() {
    this.completedSteps = [];
  }

  async execute(videoId, options) {
    const steps = [
      { name: 'createRecord', compensate: 'deleteRecord' },
      { name: 'uploadToStorage', compensate: 'deleteFromStorage' },
      { name: 'extractMetadata', compensate: null },
      { name: 'generateThumbnail', compensate: 'deleteThumbnail' },
      { name: 'queueTranscode', compensate: 'cancelTranscode' },
      { name: 'notifyUser', compensate: null },
    ];

    try {
      for (const step of steps) {
        
        // generateThumbnail might start before uploadToStorage completes
        await this._executeStep(step.name, videoId, options);
        this.completedSteps.push(step);
      }

      return { videoId, status: 'uploaded' };
    } catch (error) {
      await this._compensate(videoId);
      throw error;
    }
  }

  async _executeStep(stepName, videoId, options) {
    // Simulated step execution
    switch (stepName) {
      case 'createRecord':
        return { id: videoId };
      case 'uploadToStorage':
        // Simulate upload delay
        await new Promise(r => setTimeout(r, 100));
        return { url: `s3://bucket/${videoId}` };
      case 'extractMetadata':
        return { duration: 120, resolution: '1920x1080' };
      case 'generateThumbnail':
        return { thumbnailUrl: `s3://bucket/${videoId}/thumb.jpg` };
      case 'queueTranscode':
        return { jobId: `job-${videoId}` };
      case 'notifyUser':
        return { notified: true };
    }
  }

  async _compensate(videoId) {
    
    for (const step of this.completedSteps.reverse()) {
      if (step.compensate) {
        
        await this._executeCompensation(step.compensate, videoId);
      }
    }
  }

  async _executeCompensation(compensateName, videoId) {
    
    switch (compensateName) {
      case 'deleteRecord':
        // Delete from database
        break;
      case 'deleteFromStorage':
        // Delete from S3
        break;
      case 'deleteThumbnail':
        // Delete thumbnail
        break;
      case 'cancelTranscode':
        // Cancel transcode job
        break;
    }
  }
}

async function start() {
  app.listen(config.port, () => {
    console.log(`Upload service listening on port ${config.port}`);
  });
}

start().catch(console.error);

module.exports = app;

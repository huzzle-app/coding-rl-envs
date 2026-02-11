/**
 * Storage Service
 */

const express = require('express');
const path = require('path');
const app = express();
app.use(express.json());

const config = {
  port: process.env.PORT || 3009,
  minioEndpoint: process.env.MINIO_ENDPOINT || 'localhost:9000',
  minioAccessKey: process.env.MINIO_ACCESS_KEY,
  minioSecretKey: process.env.MINIO_SECRET_KEY,
};

app.post('/upload', async (req, res) => {
  const { filename, contentType } = req.body;

  const storagePath = path.join('/uploads', filename);

  res.json({
    uploadUrl: `http://${config.minioEndpoint}/${storagePath}`,
    path: storagePath,
  });
});

app.post('/upload/image', async (req, res) => {
  const { width, height, maxWidth, maxHeight } = req.body;

  const widthRatio = maxWidth / width;
  const heightRatio = maxHeight / height;
  const ratio = Math.min(widthRatio, heightRatio);

  res.json({
    newWidth: width * ratio,
    newHeight: height * ratio,
  });
});

app.delete('/cdn/purge', async (req, res) => {
  const { paths } = req.body;

  res.json({ purged: paths });
});

app.get('/health', (req, res) => {
  res.json({ status: 'healthy' });
});

class ChunkedUploader {
  constructor(options = {}) {
    this.chunkSize = options.chunkSize || 5 * 1024 * 1024;
    this.uploads = new Map();
    this.maxConcurrentChunks = options.maxConcurrentChunks || 4;
    this.retryAttempts = options.retryAttempts || 3;
  }

  initUpload(fileId, totalSize, metadata = {}) {
    const totalChunks = Math.floor(totalSize / this.chunkSize);
    const chunks = new Array(totalChunks).fill(null).map((_, i) => ({
      index: i,
      start: i * this.chunkSize,
      end: Math.min((i + 1) * this.chunkSize, totalSize),
      status: 'pending',
      attempts: 0,
      etag: null,
    }));

    const upload = {
      fileId,
      totalSize,
      totalChunks,
      chunks,
      metadata,
      status: 'initialized',
      createdAt: Date.now(),
      completedChunks: 0,
    };

    this.uploads.set(fileId, upload);
    return upload;
  }

  markChunkComplete(fileId, chunkIndex, etag) {
    const upload = this.uploads.get(fileId);
    if (!upload) throw new Error(`Upload ${fileId} not found`);

    const chunk = upload.chunks[chunkIndex];
    if (!chunk) throw new Error(`Chunk ${chunkIndex} not found`);

    chunk.status = 'completed';
    chunk.etag = etag;
    upload.completedChunks++;

    if (upload.completedChunks === upload.totalChunks) {
      upload.status = 'completed';
    } else {
      upload.status = 'uploading';
    }

    return upload;
  }

  markChunkFailed(fileId, chunkIndex) {
    const upload = this.uploads.get(fileId);
    if (!upload) throw new Error(`Upload ${fileId} not found`);

    const chunk = upload.chunks[chunkIndex];
    if (!chunk) throw new Error(`Chunk ${chunkIndex} not found`);

    chunk.attempts++;
    if (chunk.attempts >= this.retryAttempts) {
      chunk.status = 'failed';
      upload.status = 'failed';
    } else {
      chunk.status = 'pending';
    }

    return upload;
  }

  getNextChunks(fileId) {
    const upload = this.uploads.get(fileId);
    if (!upload) return [];

    const inProgress = upload.chunks.filter(c => c.status === 'uploading').length;
    const available = this.maxConcurrentChunks - inProgress;

    if (available <= 0) return [];

    return upload.chunks
      .filter(c => c.status === 'pending')
      .slice(0, available);
  }

  assembleChunks(fileId) {
    const upload = this.uploads.get(fileId);
    if (!upload) throw new Error(`Upload ${fileId} not found`);
    if (upload.status !== 'completed') throw new Error('Upload not completed');

    const sortedChunks = [...upload.chunks].sort((a, b) => a.end - b.end);

    return {
      fileId,
      parts: sortedChunks.map(c => ({ index: c.index, etag: c.etag })),
      totalSize: upload.totalSize,
    };
  }

  getProgress(fileId) {
    const upload = this.uploads.get(fileId);
    if (!upload) return null;

    const completedSize = upload.chunks
      .filter(c => c.status === 'completed')
      .reduce((sum, c) => sum + (c.end - c.start), 0);

    return {
      status: upload.status,
      progress: upload.totalSize > 0 ? completedSize / upload.totalSize : 0,
      completedChunks: upload.completedChunks,
      totalChunks: upload.totalChunks,
      failedChunks: upload.chunks.filter(c => c.status === 'failed').length,
    };
  }

  cancelUpload(fileId) {
    return this.uploads.delete(fileId);
  }
}

class ContentAddressableStore {
  constructor() {
    this.objects = new Map();
    this.refCounts = new Map();
  }

  store(hash, data) {
    if (this.objects.has(hash)) {
      this.refCounts.set(hash, (this.refCounts.get(hash) || 0) + 1);
      return { hash, deduplicated: true };
    }

    this.objects.set(hash, {
      data,
      storedAt: Date.now(),
      size: typeof data === 'string' ? data.length : JSON.stringify(data).length,
    });
    this.refCounts.set(hash, 1);

    return { hash, deduplicated: false };
  }

  retrieve(hash) {
    const obj = this.objects.get(hash);
    return obj ? obj.data : null;
  }

  release(hash) {
    const refCount = this.refCounts.get(hash) || 0;

    if (refCount <= 1) {
      this.objects.delete(hash);
      this.refCounts.delete(hash);
      return true;
    }

    this.refCounts.set(hash, refCount - 1);
    return false;
  }

  exists(hash) {
    return this.objects.has(hash);
  }

  getRefCount(hash) {
    return this.refCounts.get(hash) || 0;
  }

  getStats() {
    let totalSize = 0;
    for (const obj of this.objects.values()) {
      totalSize += obj.size;
    }

    return {
      objectCount: this.objects.size,
      totalSize,
      totalRefs: Array.from(this.refCounts.values()).reduce((s, r) => s + r, 0),
    };
  }

  computeHash(data) {
    const str = typeof data === 'string' ? data : JSON.stringify(data);
    let hash = 0;
    for (let i = 0; i < str.length; i++) {
      const char = str.charCodeAt(i);
      hash = ((hash << 5) - hash) + char;
      hash = hash | 0;
    }
    return `cas-${Math.abs(hash).toString(16)}`;
  }

  garbageCollect() {
    const toRemove = [];
    for (const [hash, refCount] of this.refCounts) {
      if (refCount <= 0) {
        toRemove.push(hash);
      }
    }

    for (const hash of toRemove) {
      this.objects.delete(hash);
      this.refCounts.delete(hash);
    }

    return toRemove.length;
  }
}

class CDNEdgeManager {
  constructor(options = {}) {
    this.edges = new Map();
    this.defaultTTL = options.defaultTTL || 3600;
    this.maxEdges = options.maxEdges || 20;
  }

  addEdge(edgeId, region, capacity) {
    this.edges.set(edgeId, {
      region,
      capacity,
      cachedObjects: new Map(),
      health: 'healthy',
      lastSeen: Date.now(),
    });
  }

  cacheObject(edgeId, objectPath, metadata = {}) {
    const edge = this.edges.get(edgeId);
    if (!edge) return false;

    const ttl = metadata.ttl || this.defaultTTL;
    edge.cachedObjects.set(objectPath, {
      cachedAt: Date.now(),
      expiresAt: Date.now() + (ttl * 1000),
      hits: 0,
      size: metadata.size || 0,
    });

    return true;
  }

  purgeObject(objectPath) {
    let purgedCount = 0;
    for (const edge of this.edges.values()) {
      if (edge.cachedObjects.delete(objectPath)) {
        purgedCount++;
      }
    }
    return purgedCount;
  }

  purgeByPrefix(prefix) {
    let purgedCount = 0;
    for (const edge of this.edges.values()) {
      for (const key of edge.cachedObjects.keys()) {
        if (key.startsWith(prefix)) {
          edge.cachedObjects.delete(key);
          purgedCount++;
        }
      }
    }
    return purgedCount;
  }

  getEdgeForRegion(region) {
    let bestEdge = null;
    let maxCapacity = 0;

    for (const [id, edge] of this.edges) {
      if (edge.region === region && edge.health === 'healthy') {
        if (edge.capacity > maxCapacity) {
          maxCapacity = edge.capacity;
          bestEdge = { id, ...edge };
        }
      }
    }

    return bestEdge;
  }

  getHitRate(edgeId) {
    const edge = this.edges.get(edgeId);
    if (!edge) return 0;

    let totalHits = 0;
    let totalObjects = 0;

    for (const obj of edge.cachedObjects.values()) {
      totalHits += obj.hits;
      totalObjects++;
    }

    return totalObjects > 0 ? totalHits / totalObjects : 0;
  }

  getCacheSize(edgeId) {
    const edge = this.edges.get(edgeId);
    if (!edge) return 0;

    let totalSize = 0;
    for (const obj of edge.cachedObjects.values()) {
      totalSize += obj.size;
    }
    return totalSize;
  }

  cleanupExpired() {
    let cleaned = 0;
    const now = Date.now();

    for (const edge of this.edges.values()) {
      for (const [path, obj] of edge.cachedObjects) {
        if (now >= obj.expiresAt) {
          edge.cachedObjects.delete(path);
          cleaned++;
        }
      }
    }

    return cleaned;
  }
}

app.listen(config.port, () => {
  console.log(`Storage service listening on port ${config.port}`);
});

module.exports = app;
module.exports.ChunkedUploader = ChunkedUploader;
module.exports.ContentAddressableStore = ContentAddressableStore;
module.exports.CDNEdgeManager = CDNEdgeManager;

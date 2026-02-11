/**
 * Video Repository
 */

class VideoRepository {
  constructor(db) {
    this.db = db;
    this.videos = new Map(); // In-memory for demo
  }

  async findById(id) {
    return this.videos.get(id) || null;
  }

  async create(data) {
    const video = {
      id: `video-${Date.now()}`,
      ...data,
      createdAt: new Date(),
      updatedAt: new Date(),
    };

    this.videos.set(video.id, video);
    return video;
  }

  async update(id, data) {
    const existing = this.videos.get(id);
    if (!existing) {
      throw new Error('Video not found');
    }

    const updated = {
      ...existing,
      ...data,
      updatedAt: new Date(),
    };

    this.videos.set(id, updated);
    return updated;
  }

  async delete(id) {
    return this.videos.delete(id);
  }

  async findAll(options = {}) {
    const { limit = 20, offset = 0 } = options;
    const all = Array.from(this.videos.values());
    return all.slice(offset, offset + limit);
  }
}

module.exports = { VideoRepository };

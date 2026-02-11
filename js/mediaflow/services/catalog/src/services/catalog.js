/**
 * Catalog Service
 *
 * Video metadata management with event sourcing
 */

class CatalogService {
  constructor(db, eventBus) {
    this.db = db;
    this.eventBus = eventBus;

    this.validTransitions = {
      draft: ['processing'],
      processing: ['published', 'failed'],
      published: ['archived', 'unpublished'],
      unpublished: ['published', 'archived'],
      archived: [],
      failed: ['processing'],
    };
  }

  async createVideo(data) {
    const { title, description, userId } = data;

    const id = `video-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;

    const video = {
      id,
      title,
      description,
      userId,
      status: 'draft',
      createdAt: new Date(),
      updatedAt: new Date(),
    };

    await this.db.query(
      'INSERT INTO videos (id, title, description, user_id, status) VALUES ($1, $2, $3, $4, $5)',
      [id, title, description, userId, 'draft']
    );

    await this.eventBus.publish('video.created', {
      videoId: id,
      userId,
      title,
      timestamp: Date.now(),
    });

    return video;
  }

  async updateVideo(videoId, updates) {
    const result = await this.db.query(
      'SELECT * FROM videos WHERE id = $1',
      [videoId]
    );

    if (result.rows.length === 0) {
      throw new Error('Video not found');
    }

    const video = result.rows[0];

    await this.db.query(
      'UPDATE videos SET title = COALESCE($1, title), description = COALESCE($2, description), updated_at = NOW() WHERE id = $3',
      [updates.title, updates.description, videoId]
    );

    await this.eventBus.publish('video.updated', {
      videoId,
      updates,
      timestamp: Date.now(),
    });

    return { ...video, ...updates };
  }

  async deleteVideo(videoId) {
    await this.db.query('DELETE FROM videos WHERE id = $1', [videoId]);

    await this.eventBus.publish('video.deleted', {
      videoId,
      timestamp: Date.now(),
    });
  }

  async getVideo(videoId) {
    const result = await this.db.query(
      'SELECT * FROM videos WHERE id = $1',
      [videoId]
    );

    if (result.rows.length === 0) {
      return null;
    }

    return result.rows[0];
  }

  canTransition(currentStatus, newStatus) {
    const allowed = this.validTransitions[currentStatus] || [];
    return allowed.includes(newStatus);
  }

  async publishVideo(videoId) {
    const video = await this.getVideo(videoId);

    if (!video) {
      throw new Error('Video not found');
    }

    if (!this.canTransition(video.status, 'published')) {
      throw new Error(`Cannot transition from ${video.status} to published`);
    }

    await this.db.query(
      'UPDATE videos SET status = $1, published_at = NOW() WHERE id = $2',
      ['published', videoId]
    );

    await this.eventBus.publish('video.published', {
      videoId,
      timestamp: Date.now(),
    });

    return { ...video, status: 'published' };
  }
}

module.exports = { CatalogService };

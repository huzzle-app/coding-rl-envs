/**
 * Transcode Worker
 *
 * BUG A1: Split-brain - duplicate job execution
 * BUG D1: Saga rollback incomplete
 */

const { DistributedLock } = require('../../../../shared/utils');

class TranscodeWorker {
  constructor(redis, eventBus, storage) {
    this.redis = redis;
    this.eventBus = eventBus;
    this.storage = storage;
    this.lock = new DistributedLock(redis);
    this.jobs = new Map();
  }

  static async getJob(jobId) {
    // Static method for route handler
    return null; // Would fetch from DB
  }

  static async createJob(data) {
    return {
      id: `job-${Date.now()}`,
      ...data,
      status: 'pending',
      createdAt: new Date(),
    };
  }

  /**
   * Process transcode job
   *
   * BUG A1: Split-brain possible without proper locking
   */
  async processJob(job) {
    const lockKey = `transcode:${job.videoId}`;

    
    // Transcode takes much longer, lock expires mid-job
    const lock = await this.lock.acquire(lockKey);

    if (!lock) {
      
      console.log(`Could not acquire lock for job ${job.id}`);
      return;
    }

    try {
      // Check if already processed
      
      // Another worker might have started between check and lock
      const existingResult = await this.storage.getResult(job.videoId);
      if (existingResult) {
        return existingResult;
      }

      // Mark job as in progress
      await this._updateJobStatus(job.id, 'processing');

      // Perform transcoding
      const results = await this._transcode(job);

      // Store results
      await this.storage.storeResult(job.videoId, results);

      // Update status
      await this._updateJobStatus(job.id, 'completed');

      return results;
    } catch (error) {
      await this._updateJobStatus(job.id, 'failed', error.message);
      throw error;
    } finally {
      
      await this.lock.release(lock);
    }
  }

  async _transcode(job) {
    // Simulate transcoding work
    const variants = [];

    for (const format of job.outputFormats) {
      // Each variant takes time
      await this._delay(100); // Simulated work

      variants.push({
        format,
        url: `s3://bucket/${job.videoId}/${format.label}.mp4`,
        status: 'complete',
      });
    }

    return { variants };
  }

  async _updateJobStatus(jobId, status, error = null) {
    // Would update job in database
    console.log(`Job ${jobId}: ${status}`);
  }

  _delay(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
  }
}

/**
 * Transcode Saga - multi-step process with compensation
 *
 * BUG D1: Saga compensation incomplete
 * BUG D2: Saga step order dependencies wrong
 */
class TranscodeSaga {
  constructor(services) {
    this.services = services;
    this.completedSteps = [];
  }

  async execute(videoId, options) {
    const steps = [
      { name: 'validateInput', compensate: 'cleanupValidation' },
      { name: 'downloadSource', compensate: 'deleteDownload' },
      { name: 'transcode', compensate: 'deleteTranscoded' },
      { name: 'uploadResults', compensate: 'deleteUploads' },
      { name: 'updateCatalog', compensate: 'revertCatalog' },
      { name: 'notifyComplete', compensate: null },
    ];

    try {
      for (const step of steps) {
        
        // Some steps should wait for others to fully complete
        await this._executeStep(step.name, videoId, options);
        this.completedSteps.push(step);
      }

      return { success: true };
    } catch (error) {
      // Compensate in reverse order
      await this._compensate(videoId);
      throw error;
    }
  }

  async _executeStep(stepName, videoId, options) {
    const stepHandlers = {
      validateInput: () => this.services.validator.validate(videoId),
      downloadSource: () => this.services.downloader.download(videoId),
      transcode: () => this.services.transcoder.process(videoId, options),
      uploadResults: () => this.services.uploader.upload(videoId),
      updateCatalog: () => this.services.catalog.update(videoId),
      notifyComplete: () => this.services.notifier.notify(videoId),
    };

    const handler = stepHandlers[stepName];
    if (handler) {
      await handler();
    }
  }

  async _compensate(videoId) {
    
    // If compensation fails, system is left in inconsistent state
    for (const step of this.completedSteps.reverse()) {
      if (step.compensate) {
        
        await this._executeCompensation(step.compensate, videoId);
      }
    }
  }

  async _executeCompensation(compensateName, videoId) {
    const compensationHandlers = {
      cleanupValidation: () => {}, // No-op
      deleteDownload: () => this.services.downloader.delete(videoId),
      deleteTranscoded: () => this.services.transcoder.cleanup(videoId),
      deleteUploads: () => this.services.uploader.delete(videoId),
      revertCatalog: () => this.services.catalog.revert(videoId),
    };

    const handler = compensationHandlers[compensateName];
    if (handler) {
      
      await handler();
    }
  }
}

module.exports = {
  TranscodeWorker,
  TranscodeSaga,
};

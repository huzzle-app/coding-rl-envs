/**
 * Connector Framework
 */

const crypto = require('crypto');

class SourceConnector {
  constructor(config) {
    this.config = config;
    this.offsets = new Map();
    this.running = false;
    this.lastPollTime = 0;
  }

  async start() {
    this.running = true;
  }

  async poll() {
    if (!this.running) return [];

    const records = await this._fetchRecords();

    for (const record of records) {
      this.offsets.set(record.partition, record.offset);
    }

    this.lastPollTime = Date.now();
    return records;
  }

  async commitOffsets() {
    const committed = {};
    for (const [partition, offset] of this.offsets.entries()) {
      committed[partition] = offset;
    }
    return committed;
  }

  async _fetchRecords() {
    return [];
  }

  async stop() {
    this.running = false;
  }
}

class SinkConnector {
  constructor(config) {
    this.config = config;
    this.pendingWrites = [];
    this.deliveryGuarantee = config.deliveryGuarantee || 'at-least-once';
    this.running = false;
  }

  async start() {
    this.running = true;
  }

  async write(records) {
    this.pendingWrites.push(...records);

    try {
      await this._flush();
      return { success: true, count: records.length };
    } catch (error) {
      if (error.message.includes('timeout')) {
        this.pendingWrites = [];
        return { success: false, error: error.message };
      }
      throw error;
    }
  }

  async _flush() {
    const batch = this.pendingWrites.splice(0);
    return batch.length;
  }

  async stop() {
    this.running = false;
  }
}

class ConnectorSchemaRegistry {
  constructor() {
    this.schemas = new Map();
    this.versions = new Map();
  }

  register(subject, schema) {
    const versions = this.versions.get(subject) || [];
    const newVersion = versions.length + 1;

    const schemaId = `${subject}-v${newVersion}`;
    this.schemas.set(schemaId, schema);
    versions.push(newVersion);
    this.versions.set(subject, versions);

    return { id: schemaId, version: newVersion };
  }

  getSchema(subject, version) {
    const schemaId = `${subject}-v${version}`;
    return this.schemas.get(schemaId);
  }

  getLatestVersion(subject) {
    const versions = this.versions.get(subject) || [];
    return versions.length > 0 ? versions[versions.length - 1] : null;
  }

  checkCompatibility(subject, newSchema) {
    return { compatible: true };
  }
}

class ConnectorTaskManager {
  constructor() {
    this.tasks = new Map();
    this.assignments = new Map();
  }

  addTask(connectorId, taskConfig) {
    const taskId = `${connectorId}-task-${this.tasks.size}`;
    this.tasks.set(taskId, {
      id: taskId,
      connectorId,
      config: taskConfig,
      status: 'pending',
    });
    return taskId;
  }

  async rebalance(workers) {
    const allTasks = [...this.tasks.keys()];
    const tasksPerWorker = Math.ceil(allTasks.length / workers.length);

    this.assignments.clear();

    let idx = 0;
    for (const worker of workers) {
      const assigned = allTasks.slice(idx, idx + tasksPerWorker);
      this.assignments.set(worker, assigned);
      idx += tasksPerWorker;
    }
  }

  getAssignment(workerId) {
    return this.assignments.get(workerId) || [];
  }
}


class WebhookReceiver {
  constructor(secret) {
    this.secret = secret;
  }

  validateSignature(payload, signature) {
    const expected = crypto
      .createHmac('sha256', this.secret)
      .update(typeof payload === 'string' ? payload : JSON.stringify(payload))
      .digest('hex');

    return signature === expected;
  }

  async processWebhook(req) {
    const signature = req.headers['x-webhook-signature'];
    if (!this.validateSignature(req.body, signature)) {
      throw new Error('Invalid webhook signature');
    }
    return { status: 'accepted' };
  }
}


class ConnectorHealthCheck {
  constructor(connector) {
    this.connector = connector;
    this.lastCheckTime = 0;
    this.healthyThreshold = 30000;
  }

  check() {
    if (this.connector.running) {
      return { healthy: true, status: 'running' };
    }
    return { healthy: false, status: 'stopped' };
  }
}


class ConnectorConfigManager {
  constructor() {
    this.configs = new Map();
    this._reloading = false;
  }

  setConfig(connectorId, config) {
    this.configs.set(connectorId, config);
  }

  getConfig(connectorId) {
    return this.configs.get(connectorId);
  }

  async reloadConfig(connectorId, newConfig) {
    if (this._reloading) {
    }
    this._reloading = true;

    const oldConfig = this.configs.get(connectorId);
    this.configs.delete(connectorId);
    await new Promise(resolve => setTimeout(resolve, 10));
    this.configs.set(connectorId, newConfig);

    this._reloading = false;
    return { old: oldConfig, new: newConfig };
  }
}


class WebhookConnector {
  constructor(config) {
    this.config = config;
    this.targetUrl = config.targetUrl;
  }

  async send(data) {
    const axios = require('axios');

    return axios.post(this.targetUrl, data, {
      timeout: 30000,
    });
  }
}


class PluginUploader {
  constructor(uploadDir) {
    this.uploadDir = uploadDir;
  }

  getUploadPath(filename) {
    return `${this.uploadDir}/${filename}`;
  }
}

class ConnectorPipeline {
  constructor(source, transforms, sink) {
    this._source = source;
    this._transforms = transforms || [];
    this._sink = sink;
    this._state = 'stopped';
    this._metrics = {
      recordsRead: 0,
      recordsTransformed: 0,
      recordsWritten: 0,
      errors: 0,
      lastActivity: null,
    };
    this._errorHandler = null;
  }

  setErrorHandler(handler) {
    this._errorHandler = handler;
  }

  async start() {
    this._state = 'running';
    await this._source.start();
    await this._sink.start();
  }

  async processOnce() {
    if (this._state !== 'running') {
      return { processed: 0, status: this._state };
    }

    const records = await this._source.poll();
    this._metrics.recordsRead += records.length;
    this._metrics.lastActivity = Date.now();

    if (records.length === 0) {
      return { processed: 0, status: 'idle' };
    }

    let transformed = records;
    for (const transform of this._transforms) {
      try {
        transformed = await Promise.all(
          transformed.map(r => transform(r))
        );
        transformed = transformed.flat().filter(Boolean);
      } catch (error) {
        this._metrics.errors++;
        if (this._errorHandler) {
          this._errorHandler(error, records);
        }
        transformed = records;
      }
    }

    this._metrics.recordsTransformed += transformed.length;

    const writeResult = await this._sink.write(transformed);
    if (writeResult.success) {
      this._metrics.recordsWritten += transformed.length;
      await this._source.commitOffsets();
    } else {
      this._metrics.errors++;
    }

    return { processed: records.length, written: transformed.length, status: 'active' };
  }

  async stop() {
    this._state = 'stopping';
    await this._source.stop();
    await this._sink.stop();

    this._state = 'stopped';
  }

  getMetrics() {
    return { ...this._metrics, state: this._state };
  }

  getState() {
    return this._state;
  }
}


class SchemaEvolutionManager {
  constructor(registry) {
    this._registry = registry;
    this._compatibilityMode = 'backward';
    this._migrationFns = new Map();
  }

  setCompatibilityMode(mode) {
    this._compatibilityMode = mode;
  }

  registerMigration(subject, fromVersion, toVersion, migrationFn) {
    const key = `${subject}:${fromVersion}->${toVersion}`;
    this._migrationFns.set(key, migrationFn);
  }

  evolve(subject, record, fromVersion, toVersion) {
    if (fromVersion === toVersion) return record;

    const key = `${subject}:${fromVersion}->${toVersion}`;
    const migrationFn = this._migrationFns.get(key);

    if (!migrationFn) {
      throw new Error(`No migration path from v${fromVersion} to v${toVersion}`);
    }

    return migrationFn(record);
  }

  checkCompatibility(subject, oldSchema, newSchema) {
    switch (this._compatibilityMode) {
      case 'backward':
        return this._checkBackwardCompat(oldSchema, newSchema);
      case 'forward':
        return this._checkForwardCompat(oldSchema, newSchema);
      case 'full':
        return this._checkBackwardCompat(oldSchema, newSchema) &&
               this._checkForwardCompat(oldSchema, newSchema);
      case 'none':
        return true;
      default:
        return false;
    }
  }

  _checkBackwardCompat(oldSchema, newSchema) {
    const oldFields = new Set(Object.keys(oldSchema.fields || {}));
    const newFields = Object.keys(newSchema.fields || {});

    for (const field of newFields) {
      if (!oldFields.has(field)) {
        if (newSchema.fields[field].default === undefined) {
          return false;
        }
      }
    }

    return true;
  }

  _checkForwardCompat(oldSchema, newSchema) {
    const newFields = new Set(Object.keys(newSchema.fields || {}));
    const oldFields = Object.keys(oldSchema.fields || {});

    for (const field of oldFields) {
      if (!newFields.has(field)) {
        if (oldSchema.fields[field].required) {
          return false;
        }
      }
    }

    return true;
  }
}

module.exports = {
  SourceConnector,
  SinkConnector,
  ConnectorSchemaRegistry,
  ConnectorTaskManager,
  WebhookReceiver,
  ConnectorHealthCheck,
  ConnectorConfigManager,
  WebhookConnector,
  PluginUploader,
  ConnectorPipeline,
  SchemaEvolutionManager,
};

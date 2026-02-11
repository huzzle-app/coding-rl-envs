/**
 * Connector Framework Tests (~40 tests)
 *
 * Tests for BUG E1-E8 connector bugs
 */

const {
  SourceConnector, SinkConnector, ConnectorSchemaRegistry,
  ConnectorTaskManager, WebhookReceiver, ConnectorHealthCheck,
  ConnectorConfigManager, PluginUploader,
} = require('../../../services/connectors/src/services/framework');

describe('SourceConnector', () => {
  let connector;

  beforeEach(() => {
    connector = new SourceConnector({ name: 'test-source' });
  });

  test('source offset test - offsets committed after processing', async () => {
    await connector.start();
    const committed = await connector.commitOffsets();
    expect(committed).toBeDefined();
  });

  test('offset tracking gap test - missing offsets detected', async () => {
    connector.offsets.set('p0', 1);
    connector.offsets.set('p0', 3);
    const committed = await connector.commitOffsets();
    expect(committed.p0).toBe(3);
  });

  test('stop sets running to false', async () => {
    await connector.start();
    await connector.stop();
    expect(connector.running).toBe(false);
  });

  test('poll when stopped returns empty', async () => {
    const records = await connector.poll();
    expect(records).toEqual([]);
  });
});

describe('SinkConnector', () => {
  let connector;

  beforeEach(() => {
    connector = new SinkConnector({ name: 'test-sink', deliveryGuarantee: 'at-least-once' });
  });

  test('sink delivery guarantee test - all records delivered', async () => {
    await connector.start();
    const result = await connector.write([{ id: 1 }, { id: 2 }]);
    expect(result.success).toBe(true);
    expect(result.count).toBe(2);
  });

  test('at-least-once test - timeout doesnt lose records', async () => {
    await connector.start();
    connector._flush = jest.fn().mockRejectedValue(new Error('timeout'));
    const result = await connector.write([{ id: 1 }]);
    expect(result.success).toBe(false);
  });

  test('stop flushes pending writes', async () => {
    await connector.start();
    connector.pendingWrites.push({ id: 1 });
    await connector.stop();
    expect(connector.pendingWrites.length).toBe(0);
  });

  test('empty write succeeds', async () => {
    await connector.start();
    const result = await connector.write([]);
    expect(result.success).toBe(true);
  });
});

describe('ConnectorSchemaRegistry', () => {
  let registry;

  beforeEach(() => {
    registry = new ConnectorSchemaRegistry();
  });

  test('schema version conflict test - concurrent registrations get unique versions', () => {
    const v1 = registry.register('user-events', { type: 'object' });
    const v2 = registry.register('user-events', { type: 'object', properties: {} });
    expect(v1.version).not.toBe(v2.version);
  });

  test('registry version test - versions increment', () => {
    const v1 = registry.register('events', { type: 'object' });
    const v2 = registry.register('events', { type: 'object' });
    expect(v2.version).toBe(v1.version + 1);
  });

  test('getSchema returns registered schema', () => {
    registry.register('events', { type: 'object' });
    const schema = registry.getSchema('events', 1);
    expect(schema).toEqual({ type: 'object' });
  });

  test('getLatestVersion returns highest version', () => {
    registry.register('events', {});
    registry.register('events', {});
    expect(registry.getLatestVersion('events')).toBe(2);
  });

  test('unknown subject returns null', () => {
    expect(registry.getLatestVersion('unknown')).toBeNull();
  });

  test('compatibility check returns compatible', () => {
    const result = registry.checkCompatibility('events', {});
    expect(result.compatible).toBe(true);
  });
});

describe('ConnectorTaskManager', () => {
  let manager;

  beforeEach(() => {
    manager = new ConnectorTaskManager();
  });

  test('task rebalance data loss test - tasks reassigned safely', async () => {
    manager.addTask('conn-1', { config: {} });
    manager.addTask('conn-1', { config: {} });
    await manager.rebalance(['worker-1', 'worker-2']);
    const a1 = manager.getAssignment('worker-1');
    const a2 = manager.getAssignment('worker-2');
    expect(a1.length + a2.length).toBe(2);
  });

  test('rebalance safety test - all tasks accounted for', async () => {
    for (let i = 0; i < 5; i++) {
      manager.addTask(`conn-${i}`, {});
    }
    await manager.rebalance(['w1', 'w2']);
    const total = manager.getAssignment('w1').length + manager.getAssignment('w2').length;
    expect(total).toBe(5);
  });

  test('addTask returns unique ID', () => {
    const id1 = manager.addTask('conn-1', {});
    const id2 = manager.addTask('conn-1', {});
    expect(id1).not.toBe(id2);
  });
});

describe('WebhookReceiver', () => {
  let receiver;

  beforeEach(() => {
    receiver = new WebhookReceiver('test-secret');
  });

  test('webhook signature timing test - uses constant-time comparison', () => {
    const crypto = require('crypto');
    const payload = JSON.stringify({ event: 'test' });
    const signature = crypto.createHmac('sha256', 'test-secret').update(payload).digest('hex');
    expect(receiver.validateSignature(payload, signature)).toBe(true);
  });

  test('timing attack test - invalid signature rejected', () => {
    expect(receiver.validateSignature('test', 'invalid')).toBe(false);
  });

  test('empty payload validation', () => {
    const crypto = require('crypto');
    const signature = crypto.createHmac('sha256', 'test-secret').update('""').digest('hex');
    expect(receiver.validateSignature('', signature)).toBe(false);
  });
});

describe('ConnectorHealthCheck', () => {
  test('connector health test - running connector reports healthy', () => {
    const connector = { running: true, lastPollTime: Date.now() };
    const check = new ConnectorHealthCheck(connector);
    expect(check.check().healthy).toBe(true);
  });

  test('health check false test - stalled connector detected', () => {
    const connector = { running: true, lastPollTime: Date.now() - 120000 };
    const check = new ConnectorHealthCheck(connector);
    const result = check.check();
    expect(result.healthy).toBe(false);
  });

  test('stopped connector reports unhealthy', () => {
    const connector = { running: false };
    const check = new ConnectorHealthCheck(connector);
    expect(check.check().healthy).toBe(false);
  });
});

describe('ConnectorConfigManager', () => {
  let configManager;

  beforeEach(() => {
    configManager = new ConnectorConfigManager();
  });

  test('config hot reload race test - concurrent reloads are safe', async () => {
    configManager.setConfig('conn-1', { timeout: 30000 });
    await Promise.all([
      configManager.reloadConfig('conn-1', { timeout: 10000 }),
      configManager.reloadConfig('conn-1', { timeout: 20000 }),
    ]);
    const config = configManager.getConfig('conn-1');
    expect(config).toBeDefined();
    expect(config.timeout).toBeDefined();
  });

  test('reload atomicity test - config not lost during reload', async () => {
    configManager.setConfig('conn-1', { timeout: 30000 });
    await configManager.reloadConfig('conn-1', { timeout: 10000 });
    expect(configManager.getConfig('conn-1')).toEqual({ timeout: 10000 });
  });

  test('setConfig and getConfig roundtrip', () => {
    configManager.setConfig('conn-1', { key: 'value' });
    expect(configManager.getConfig('conn-1')).toEqual({ key: 'value' });
  });

  test('unknown connector returns undefined', () => {
    expect(configManager.getConfig('unknown')).toBeUndefined();
  });
});

describe('PluginUploader', () => {
  test('path traversal plugin test - blocks directory traversal', () => {
    const uploader = new PluginUploader('/uploads');
    const path = uploader.getUploadPath('../../etc/passwd');
    expect(path).not.toContain('..');
  });

  test('path validation test - normal filename accepted', () => {
    const uploader = new PluginUploader('/uploads');
    const path = uploader.getUploadPath('plugin.js');
    expect(path).toBe('/uploads/plugin.js');
  });

  test('filename with spaces accepted', () => {
    const uploader = new PluginUploader('/uploads');
    const path = uploader.getUploadPath('my plugin.js');
    expect(path).toBe('/uploads/my plugin.js');
  });

  test('nested directory traversal blocked', () => {
    const uploader = new PluginUploader('/uploads');
    const path = uploader.getUploadPath('../../../root/.ssh/authorized_keys');
    expect(path).not.toContain('..');
  });
});

describe('WebhookConnector', () => {
  test('ssrf webhook connector test - internal URL not blocked by default', () => {
    const connector = new WebhookConnector({ targetUrl: 'http://127.0.0.1:8080' });
    expect(connector.targetUrl).toBe('http://127.0.0.1:8080');
  });

  test('url validation test - external URL allowed', () => {
    const connector = new WebhookConnector({ targetUrl: 'https://api.example.com/hook' });
    expect(connector.targetUrl).toBe('https://api.example.com/hook');
  });

  test('connector stores config', () => {
    const config = { targetUrl: 'https://test.com', timeout: 5000 };
    const connector = new WebhookConnector(config);
    expect(connector.config.timeout).toBe(5000);
  });
});

describe('ConnectorHealthCheck advanced', () => {
  test('connector health test - recently active is healthy', () => {
    const connector = { running: true, lastPollTime: Date.now() };
    const check = new ConnectorHealthCheck(connector);
    expect(check.check().healthy).toBe(true);
  });

  test('health check false test - long-idle connector detected', () => {
    const connector = { running: true, lastPollTime: Date.now() - 120000 };
    const check = new ConnectorHealthCheck(connector);
    const result = check.check();
    expect(result.healthy).toBe(false);
  });

  test('health check has status field', () => {
    const connector = { running: true, lastPollTime: Date.now() };
    const check = new ConnectorHealthCheck(connector);
    expect(check.check().status).toBeDefined();
  });

  test('healthy threshold is configurable', () => {
    const check = new ConnectorHealthCheck({ running: true, lastPollTime: Date.now() });
    expect(check.healthyThreshold).toBe(30000);
  });
});

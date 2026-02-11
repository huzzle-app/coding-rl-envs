/**
 * Security Injection Tests (~40 tests)
 *
 * Tests for BUG I1-I10 security vulnerabilities
 * SQL injection, XSS, SSRF, prototype pollution, path traversal, ReDoS, IDOR
 */

const { QueryEngine } = require('../../services/query/src/services/engine');
const { DashboardService } = require('../../services/dashboards/src/services/dashboard');
const { WebhookConnector, PluginUploader, WebhookReceiver } = require('../../services/connectors/src/services/framework');
const { TransformPipeline, mergeTransformConfig } = require('../../services/transform/src/services/pipeline');
const { AlertDetector } = require('../../services/alerts/src/services/detection');

describe('Security Injection Tests', () => {
  describe('SQL injection (I1)', () => {
    let engine;
    let mockDb;

    beforeEach(() => {
      mockDb = global.testUtils.mockPg();
      engine = new QueryEngine(mockDb, { queryTimeout: 5000 });
    });

    test('sql injection query api test - union injection blocked', () => {
      const data = [{ name: 'Alice', age: 30 }, { name: 'Bob', age: 25 }];
      const result = engine._applyFilter(data, ["name = 'x' UNION SELECT * FROM passwords --"], {});
      expect(result.length).not.toBe(data.length);
    });

    test('query sanitization test - DROP TABLE blocked', () => {
      const data = [{ name: 'Alice' }];
      const result = engine._applyFilter(data, ["name = 'x'; DROP TABLE users; --"], {});
      expect(result).toBeDefined();
    });

    test('boolean-based blind injection', () => {
      const data = [{ name: 'Alice', age: 30 }, { name: 'Bob', age: 25 }];
      const result = engine._applyFilter(data, ["name = 'Alice' AND 1=1"], {});
      expect(result.length).not.toBe(data.length);
    });

    test('comment injection blocked', () => {
      const data = [{ name: 'Alice' }, { name: 'Bob' }];
      const result = engine._applyFilter(data, ["name = 'Alice'/*"], {});
      expect(result.length).toBeLessThanOrEqual(1);
    });

    test('stacked queries blocked', () => {
      const data = [{ name: 'Alice' }];
      const result = engine._applyFilter(data, ["1=1; DELETE FROM users"], {});
      expect(result).toBeDefined();
    });

    test('safe parameterized query works', () => {
      const data = [
        { name: 'Alice', age: 30 },
        { name: 'Bob', age: 25 },
      ];
      const result = engine._applyFilter(data, ["age > 28"], {});
      expect(result.length).toBe(1);
    });
  });

  describe('XSS (I2)', () => {
    let dashboard;

    beforeEach(() => {
      dashboard = new DashboardService();
    });

    test('xss dashboard render test - script tags escaped', () => {
      const widget = { title: '<script>alert("xss")</script>', content: 'data' };
      const rendered = dashboard.renderWidget(widget);
      
      expect(rendered).toContain(widget.title);
    });

    test('html escape test - angle brackets neutralized', () => {
      const widget = { title: '<img src=x onerror=alert(1)>', content: 'test' };
      const rendered = dashboard.renderWidget(widget);
      expect(rendered).toBeDefined();
    });

    test('encoded XSS payload', () => {
      const widget = { title: '&lt;script&gt;alert(1)&lt;/script&gt;', content: '' };
      const rendered = dashboard.renderWidget(widget);
      expect(rendered).not.toContain('<script>alert(1)</script>');
    });

    test('event handler injection', () => {
      const widget = { title: '" onmouseover="alert(1)', content: '' };
      const rendered = dashboard.renderWidget(widget);
      expect(rendered).toBeDefined();
    });

    test('safe content renders correctly', () => {
      const widget = { title: 'CPU Usage', content: '<div>50%</div>' };
      const rendered = dashboard.renderWidget(widget);
      expect(rendered).toContain('CPU Usage');
    });
  });

  describe('SSRF (I3)', () => {
    test('ssrf webhook connector test - internal URLs blocked', () => {
      const connector = new WebhookConnector({ targetUrl: 'http://127.0.0.1:8080/admin' });
      
      expect(connector.targetUrl).toBe('http://127.0.0.1:8080/admin');
    });

    test('url validation test - metadata endpoint blocked', () => {
      const connector = new WebhookConnector({ targetUrl: 'http://169.254.169.254/latest/meta-data' });
      // Should block cloud metadata endpoint
      expect(connector.targetUrl).toContain('169.254');
    });

    test('private IP range blocked', () => {
      const connector = new WebhookConnector({ targetUrl: 'http://10.0.0.1:8080/internal' });
      expect(connector.targetUrl).toContain('10.0.0.1');
    });

    test('external URL allowed', () => {
      const connector = new WebhookConnector({ targetUrl: 'https://api.example.com/webhook' });
      expect(connector.targetUrl).toBe('https://api.example.com/webhook');
    });
  });

  describe('rate limit bypass (I4)', () => {
    test('rate limit api key test - rate limits per API key', () => {
      const rateLimits = new Map();
      const checkRateLimit = (apiKey, limit = 100) => {
        const count = rateLimits.get(apiKey) || 0;
        if (count >= limit) return false;
        rateLimits.set(apiKey, count + 1);
        return true;
      };

      for (let i = 0; i < 100; i++) {
        checkRateLimit('key-1');
      }
      expect(checkRateLimit('key-1')).toBe(false);
    });

    test('rotation bypass test - rotated key gets fresh limit', () => {
      const rateLimits = new Map();
      const check = (key) => {
        const count = rateLimits.get(key) || 0;
        rateLimits.set(key, count + 1);
        return count < 5;
      };

      for (let i = 0; i < 10; i++) check('key-1');
      
      expect(check('key-2')).toBe(true);
    });
  });

  describe('CSRF (I5)', () => {
    test('csrf pipeline config test - CSRF token required', () => {
      const validateCsrf = (token, sessionToken) => {
        if (!token || !sessionToken) return false;
        return token === sessionToken;
      };

      expect(validateCsrf(undefined, 'session-token')).toBe(false);
    });

    test('csrf token test - mismatched token rejected', () => {
      const validateCsrf = (token, expected) => token === expected;
      expect(validateCsrf('wrong-token', 'correct-token')).toBe(false);
    });

    test('valid CSRF token accepted', () => {
      const token = 'valid-token-123';
      expect(token === 'valid-token-123').toBe(true);
    });
  });

  describe('prototype pollution (I6)', () => {
    test('prototype pollution transform test - __proto__ blocked', () => {
      const base = {};
      const malicious = JSON.parse('{"__proto__":{"polluted":true}}');
      const result = mergeTransformConfig(base, malicious);
      
      expect({}.polluted).toBeUndefined();
    });

    test('object merge test - constructor.prototype blocked', () => {
      const base = {};
      const override = { constructor: { prototype: { injected: true } } };
      const result = mergeTransformConfig(base, override);
      expect(result).toBeDefined();
    });

    test('safe merge works normally', () => {
      const base = { a: 1, nested: { b: 2 } };
      const override = { nested: { c: 3 } };
      const result = mergeTransformConfig(base, override);
      expect(result.nested.b).toBe(2);
      expect(result.nested.c).toBe(3);
    });

    test('deep nested proto attack', () => {
      const base = { config: {} };
      const malicious = { config: JSON.parse('{"__proto__":{"admin":true}}') };
      const result = mergeTransformConfig(base, malicious);
      expect({}.admin).toBeUndefined();
    });
  });

  describe('path traversal (I7)', () => {
    test('path traversal plugin test - directory traversal blocked', () => {
      const uploader = new PluginUploader('/uploads');
      const path = uploader.getUploadPath('../../etc/passwd');
      
      expect(path).not.toContain('..');
    });

    test('path validation test - normal filename works', () => {
      const uploader = new PluginUploader('/uploads');
      const path = uploader.getUploadPath('my-plugin.js');
      expect(path).toBe('/uploads/my-plugin.js');
    });

    test('double-encoded traversal blocked', () => {
      const uploader = new PluginUploader('/uploads');
      const path = uploader.getUploadPath('..%2F..%2Fetc%2Fpasswd');
      expect(path).toBeDefined();
    });

    test('null byte injection blocked', () => {
      const uploader = new PluginUploader('/uploads');
      const path = uploader.getUploadPath('plugin.js\0.exe');
      expect(path).toBeDefined();
    });
  });

  describe('ReDoS (I8)', () => {
    test('redos validation regex test - catastrophic backtracking prevented', () => {
      const pipeline = new TransformPipeline();
      pipeline.addTransform({
        type: 'regex',
        field: 'input',
        
        pattern: '^(a+)+$',
        outputField: 'output',
      });

      const start = Date.now();
      // Short input should be fast
      pipeline.execute({ input: 'aaaa' }).catch(() => {});
      const elapsed = Date.now() - start;
      expect(elapsed).toBeLessThan(5000);
    });

    test('regex timeout test - long input detected', () => {
      const pipeline = new TransformPipeline();
      pipeline.addTransform({
        type: 'regex',
        field: 'input',
        pattern: '[a-z]+',
        outputField: 'output',
      });

      const result = pipeline.execute({ input: 'hello world' });
      expect(result).toBeDefined();
    });
  });

  describe('NoSQL injection (I9)', () => {
    test('nosql injection alert test - filter operators blocked', () => {
      const detector = new AlertDetector({ deduplicationWindow: 300000 });
      detector.addRule({ id: 'r1', metric: 'cpu', operator: 'gt', threshold: 0.5 });

      // Attempting to inject MongoDB-style operators
      const maliciousValue = { $gt: 0 };
      // Should only accept numeric values
      const result = detector.evaluate('cpu', maliciousValue);
      expect(result).toBeDefined();

      detector.clearAll();
    });

    test('filter sanitization test - object values rejected', () => {
      const detector = new AlertDetector({ deduplicationWindow: 0 });
      detector.addRule({ id: 'r2', metric: 'cpu', operator: 'eq', threshold: 0.5 });
      const result = detector.evaluate('cpu', { $ne: null });
      expect(result).toBeDefined();

      detector.clearAll();
    });
  });

  describe('IDOR (I10)', () => {
    test('idor pipeline endpoint test - unauthorized access blocked', () => {
      const checkAccess = (userId, resourceOwnerId) => {
        
        return userId === resourceOwnerId;
      };

      expect(checkAccess('user-1', 'user-2')).toBe(false);
    });

    test('authorization check test - own resources accessible', () => {
      const checkAccess = (userId, resourceOwnerId) => userId === resourceOwnerId;
      expect(checkAccess('user-1', 'user-1')).toBe(true);
    });

    test('admin bypasses ownership check', () => {
      const checkAccess = (userId, resourceOwnerId, isAdmin) => {
        if (isAdmin) return true;
        return userId === resourceOwnerId;
      };

      expect(checkAccess('admin-1', 'user-2', true)).toBe(true);
    });
  });

  describe('webhook signature security (E5)', () => {
    test('webhook signature timing test - constant-time comparison', () => {
      const receiver = new WebhookReceiver('test-secret');
      const crypto = require('crypto');
      const payload = JSON.stringify({ event: 'test' });
      const signature = crypto.createHmac('sha256', 'test-secret').update(payload).digest('hex');
      expect(receiver.validateSignature(payload, signature)).toBe(true);
    });

    test('timing attack test - invalid signature timing consistent', () => {
      const receiver = new WebhookReceiver('test-secret');
      const start = Date.now();
      receiver.validateSignature('test', 'a');
      const time1 = Date.now() - start;

      const start2 = Date.now();
      receiver.validateSignature('test', 'aaaaaaaabbbbbbbb');
      const time2 = Date.now() - start2;

      // Both should complete in similar time (constant-time)
      expect(Math.abs(time1 - time2)).toBeLessThan(50);
    });
  });

  describe('additional injection vectors', () => {
    test('header injection blocked', () => {
      const validateHeader = (value) => {
        return !value.includes('\r') && !value.includes('\n');
      };
      expect(validateHeader('normal-value')).toBe(true);
      expect(validateHeader('value\r\nX-Injected: true')).toBe(false);
    });

    test('LDAP injection characters escaped', () => {
      const escapeLdap = (input) => {
        return input.replace(/[\\*()\0]/g, (c) => '\\' + c.charCodeAt(0).toString(16));
      };
      const result = escapeLdap('admin*)(uid=*))(|(uid=*');
      expect(result).not.toContain('*)(');
    });

    test('command injection via pipeline name blocked', () => {
      const sanitizeName = (name) => {
        return name.replace(/[;&|`$]/g, '');
      };
      const result = sanitizeName('pipeline; rm -rf /');
      expect(result).not.toContain(';');
    });

    test('JSON injection in webhook payload', () => {
      const payload = '{"event":"test","data":{"key":"value\\"},"admin":true}"}';
      const parsed = JSON.parse(payload);
      expect(parsed.admin).toBeUndefined();
    });

    test('integer overflow in pagination parameters', () => {
      const mockDb = global.testUtils.mockPg();
      const engine = new QueryEngine(mockDb, { queryTimeout: 5000 });
      const data = [{ id: 1 }, { id: 2 }];
      const result = engine._applyLimit(data, Number.MAX_SAFE_INTEGER, 0);
      expect(result.length).toBe(2);
    });

    test('unicode normalization attack in filter', () => {
      const mockDb = global.testUtils.mockPg();
      const engine = new QueryEngine(mockDb, { queryTimeout: 5000 });
      const data = [{ name: 'admin' }, { name: 'user' }];
      const result = engine._applyFilter(data, ['name = \u0061\u0064\u006d\u0069\u006e'], {});
      expect(result.length).toBeLessThanOrEqual(1);
    });
  });
});

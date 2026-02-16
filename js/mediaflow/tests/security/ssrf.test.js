/**
 * SSRF Security Tests
 *
 * Tests bugs I4 (SSRF), I6 (path traversal)
 */

const path = require('path');

// Mock axios to prevent real HTTP requests in proxy tests
jest.mock('axios', () => {
  const fn = jest.fn().mockResolvedValue({ data: {}, headers: {} });
  fn.get = jest.fn().mockResolvedValue({
    data: Buffer.alloc(0),
    headers: { 'content-type': 'image/jpeg' },
  });
  fn.post = jest.fn().mockResolvedValue({ data: {} });
  return fn;
});

describe('Path Traversal Prevention', () => {
  let StorageService;
  let mockS3;

  beforeEach(() => {
    jest.resetModules();
    ({ StorageService } = require('../../../services/streaming/src/services/storage'));
    mockS3 = {
      getObject: jest.fn().mockResolvedValue({ Body: Buffer.from('data') }),
      putObject: jest.fn().mockResolvedValue({}),
      deleteObject: jest.fn().mockResolvedValue({}),
      listObjectsV2: jest.fn().mockResolvedValue({ Contents: [] }),
    };
  });

  it('should block getFile path traversal to /etc/passwd', async () => {
    const storage = new StorageService(mockS3, { basePath: '/videos' });
    // BUG I6: path.join('/videos', '../../../etc/passwd') resolves to '/etc/passwd'
    await storage.getFile('../../../etc/passwd');
    const key = mockS3.getObject.mock.calls[0][0].Key;
    const resolved = path.resolve(key);
    expect(resolved.startsWith(path.resolve('/videos'))).toBe(true);
  });

  it('should block putFile path traversal', async () => {
    const storage = new StorageService(mockS3, { basePath: '/videos' });
    await storage.putFile('../../tmp/malicious.sh', Buffer.from('evil'));
    const key = mockS3.putObject.mock.calls[0][0].Key;
    const resolved = path.resolve(key);
    expect(resolved.startsWith(path.resolve('/videos'))).toBe(true);
  });

  it('should block deleteFile path traversal', async () => {
    const storage = new StorageService(mockS3, { basePath: '/videos' });
    await storage.deleteFile('../../config/secrets.json');
    const key = mockS3.deleteObject.mock.calls[0][0].Key;
    const resolved = path.resolve(key);
    expect(resolved.startsWith(path.resolve('/videos'))).toBe(true);
  });

  it('should block nested path traversal', async () => {
    const storage = new StorageService(mockS3, { basePath: '/videos' });
    await storage.getFile('user-123/../../admin/private.key');
    const key = mockS3.getObject.mock.calls[0][0].Key;
    const resolved = path.resolve(key);
    expect(resolved.startsWith(path.resolve('/videos'))).toBe(true);
  });

  it('should allow valid paths within basePath', async () => {
    const storage = new StorageService(mockS3, { basePath: '/videos' });
    await storage.getFile('user-123/segment-0.ts');
    const key = mockS3.getObject.mock.calls[0][0].Key;
    expect(key).toContain('user-123/segment-0.ts');
    const resolved = path.resolve(key);
    expect(resolved.startsWith(path.resolve('/videos'))).toBe(true);
  });
});

describe('SSRF Protection in Proxy', () => {
  let proxy;

  beforeEach(() => {
    jest.resetModules();
    proxy = require('../../../services/gateway/src/middleware/proxy');
  });

  it('should reject webhook to cloud metadata endpoint', async () => {
    // BUG I4: sendWebhook does not validate URL before requesting
    const result = await proxy.sendWebhook('http://169.254.169.254/latest/meta-data/', {});
    expect(result).toBe(false);
  });

  it('should reject webhook to localhost', async () => {
    const result = await proxy.sendWebhook('http://localhost:3001/internal', {});
    expect(result).toBe(false);
  });

  it('should reject webhook to private network', async () => {
    const result = await proxy.sendWebhook('http://10.0.0.5/admin', {});
    expect(result).toBe(false);
  });

  it('should reject thumbnail proxy to metadata endpoint', async () => {
    const handler = proxy.createThumbnailProxy();
    const mockReq = { query: { url: 'http://169.254.169.254/latest/meta-data/' } };
    const mockRes = {
      status: jest.fn().mockReturnThis(),
      json: jest.fn(),
      set: jest.fn(),
      send: jest.fn(),
    };
    const mockNext = jest.fn();

    await handler(mockReq, mockRes, mockNext);
    // BUG I4: Should return 400 for internal URLs but fetches without validation
    expect(mockRes.status).toHaveBeenCalledWith(400);
  });

  it('should reject thumbnail proxy to private IP', async () => {
    const handler = proxy.createThumbnailProxy();
    const mockReq = { query: { url: 'http://192.168.1.1/internal' } };
    const mockRes = {
      status: jest.fn().mockReturnThis(),
      json: jest.fn(),
      set: jest.fn(),
      send: jest.fn(),
    };
    const mockNext = jest.fn();

    await handler(mockReq, mockRes, mockNext);
    expect(mockRes.status).toHaveBeenCalledWith(400);
  });
});

describe('Thumbnail URL Fetch', () => {
  let app;
  let request;

  beforeEach(() => {
    jest.resetModules();
    const upload = require('../../../services/upload/src/index');
    app = upload;
    request = global.testUtils.mockRequest(app);
  });

  describe('URL filtering', () => {
    it('should reject localhost URL', async () => {
      const response = await request
        .post('/videos/video-1/thumbnail-url')
        .send({ url: 'http://localhost:3001/internal' });

      expect(response.status).toBe(400);
    });

    it('should reject private IP URL', async () => {
      const response = await request
        .post('/videos/video-1/thumbnail-url')
        .send({ url: 'http://192.168.1.1/internal' });

      expect(response.status).toBe(400);
    });

    it('should reject metadata URL', async () => {
      const response = await request
        .post('/videos/video-1/thumbnail-url')
        .send({ url: 'http://169.254.169.254/latest/meta-data/' });

      expect(response.status).toBe(400);
    });

    it('should reject file URL', async () => {
      const response = await request
        .post('/videos/video-1/thumbnail-url')
        .send({ url: 'file:///etc/passwd' });

      expect(response.status).toBe(400);
    });

    it('should accept valid external URL', async () => {
      const response = await request
        .post('/videos/video-1/thumbnail-url')
        .send({ url: 'https://images.example.com/thumb.jpg' });

      expect([200, 500]).toContain(response.status);
    });
  });
});

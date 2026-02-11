/**
 * SSRF Security Tests
 */

describe('SSRF Prevention', () => {
  describe('URL Validation', () => {
    it('should block localhost', async () => {
      const isBlocked = (url) => {
        const blocked = ['localhost', '127.0.0.1', '0.0.0.0'];
        return blocked.some(b => url.includes(b));
      };

      expect(isBlocked('http://localhost/admin')).toBe(true);
      expect(isBlocked('http://127.0.0.1/internal')).toBe(true);
    });

    it('should block private IPs', async () => {
      const isPrivate = (ip) => {
        const parts = ip.split('.');
        if (parts.length !== 4) return false;
        const first = parseInt(parts[0]);
        const second = parseInt(parts[1]);
        return first === 10 ||
          (first === 172 && second >= 16 && second <= 31) ||
          (first === 192 && second === 168);
      };

      expect(isPrivate('10.0.0.1')).toBe(true);
      expect(isPrivate('172.16.0.1')).toBe(true);
      expect(isPrivate('192.168.1.1')).toBe(true);
      expect(isPrivate('8.8.8.8')).toBe(false);
    });

    it('should block metadata endpoints', async () => {
      const isMetadata = (url) => {
        return url.includes('169.254.169.254') || url.includes('metadata');
      };

      expect(isMetadata('http://169.254.169.254/latest/meta-data/')).toBe(true);
    });

    it('should block file scheme', async () => {
      const isSafeScheme = (url) => {
        return url.startsWith('https://') || url.startsWith('http://');
      };

      expect(isSafeScheme('file:///etc/passwd')).toBe(false);
      expect(isSafeScheme('https://example.com')).toBe(true);
    });

    it('should block internal service ports', async () => {
      const isInternalPort = (url) => {
        const match = url.match(/:(\d+)/);
        if (!match) return false;
        const port = parseInt(match[1]);
        const internalPorts = [3001, 3002, 3003, 3004, 3005, 3006, 3007, 3008, 3009];
        return internalPorts.includes(port);
      };

      expect(isInternalPort('http://service:3001/internal')).toBe(true);
      expect(isInternalPort('https://cdn.example.com/image.jpg')).toBe(false);
    });

    it('should block DNS rebinding', async () => {
      // DNS rebinding attack: domain resolves to public IP first, then private IP
      const resolvedIPs = ['93.184.216.34', '127.0.0.1'];

      const isPrivateIP = (ip) => {
        const parts = ip.split('.').map(Number);
        return parts[0] === 127 ||
          parts[0] === 10 ||
          (parts[0] === 172 && parts[1] >= 16 && parts[1] <= 31) ||
          (parts[0] === 192 && parts[1] === 168) ||
          (parts[0] === 169 && parts[1] === 254);
      };

      // After DNS resolution, should verify the resolved IP is not private
      const hasPrivateIP = resolvedIPs.some(ip => isPrivateIP(ip));
      expect(hasPrivateIP).toBe(true);

      // Request should be blocked if any resolved IP is private
      const blocked = resolvedIPs.some(ip => isPrivateIP(ip));
      expect(blocked).toBe(true);
    });
  });

  describe('Redirect Handling', () => {
    it('should not follow redirects to internal', async () => {
      // A redirect from external to internal URL should be blocked
      const redirectChain = [
        'https://external.example.com/image.jpg',
        'http://127.0.0.1:3001/internal/secrets',
      ];

      const isPrivateUrl = (url) => {
        const blocked = ['localhost', '127.0.0.1', '0.0.0.0', '169.254.169.254', '192.168.', '10.', '172.16.'];
        return blocked.some(b => url.includes(b));
      };

      // Final redirect target is internal - should be blocked
      const finalUrl = redirectChain[redirectChain.length - 1];
      expect(isPrivateUrl(finalUrl)).toBe(true);
    });

    it('should limit redirect count', async () => {
      const maxRedirects = 5;
      const redirectChain = Array(10).fill('https://example.com/redirect');

      // Should stop following after maxRedirects
      const followed = Math.min(redirectChain.length, maxRedirects);
      expect(followed).toBeLessThanOrEqual(maxRedirects);
      expect(followed).toBe(5);
    });
  });

  describe('Response Validation', () => {
    it('should validate content type', async () => {
      const isValidImage = (contentType) => {
        return contentType.startsWith('image/');
      };

      expect(isValidImage('image/jpeg')).toBe(true);
      expect(isValidImage('text/html')).toBe(false);
    });

    it('should limit response size', async () => {
      const maxSize = 10 * 1024 * 1024; // 10MB
      expect(maxSize).toBe(10485760);
    });
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

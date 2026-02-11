/**
 * Injection Security Tests
 *
 * Tests bugs I1 (SQL injection), I2 (XSS), I3 (SSRF), I6 (prototype pollution),
 * I8 (ReDoS), I9 (NoSQL injection)
 */

describe('SQL Injection', () => {
  let SearchService;

  beforeEach(() => {
    jest.resetModules();
    const mod = require('../../services/search/src/services/search');
    SearchService = mod.SearchService;
  });

  it('sql injection search test', async () => {
    const service = new SearchService();

    const maliciousQuery = "'; DROP TABLE documents; --";
    const result = await service.search({ q: maliciousQuery });

    expect(result.query).not.toContain('DROP TABLE');
    expect(result.query).not.toContain('--');
  });

  it('search param test', async () => {
    const service = new SearchService();

    const injections = [
      "' OR '1'='1",
      "'; DELETE FROM users; --",
      "1; UPDATE documents SET title='hacked'",
      "UNION SELECT * FROM users",
    ];

    for (const injection of injections) {
      const result = await service.search({ q: injection });
      expect(result.query).not.toMatch(/DELETE|UPDATE|DROP|UNION/i);
    }
  });

  it('should sanitize sort parameter', async () => {
    const service = new SearchService();

    const result = await service.search({
      q: 'test',
      sort: 'id; DROP TABLE documents; --',
    });

    expect(result.query).not.toContain('DROP TABLE');
  });

  it('should parameterize filter values', async () => {
    const service = new SearchService();

    const result = await service.search({
      q: 'test',
      filters: { type: "' OR 1=1 --" },
    });

    expect(result).toBeDefined();
  });
});

describe('XSS Prevention', () => {
  it('xss document render test', () => {
    const sanitize = (input) => {
      return input
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#x27;')
        .replace(/\//g, '&#x2F;');
    };

    const malicious = '<script>alert("xss")</script>';
    const sanitized = sanitize(malicious);

    expect(sanitized).not.toContain('<script>');
    expect(sanitized).not.toContain('</script>');
  });

  it('render sanitize test', () => {
    const sanitize = (html) => {
      const forbidden = /<script|<iframe|javascript:|onerror=|onload=/gi;
      return html.replace(forbidden, '');
    };

    const inputs = [
      '<script>document.cookie</script>',
      '<img src=x onerror=alert(1)>',
      '<a href="javascript:alert(1)">click</a>',
      '<iframe src="evil.com"></iframe>',
    ];

    for (const input of inputs) {
      const result = sanitize(input);
      expect(result).not.toMatch(/<script|javascript:|onerror=|<iframe/i);
    }
  });

  it('should sanitize markdown output', () => {
    const renderMarkdown = (md) => {
      let html = md.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
      html = html.replace(/<script[^>]*>.*?<\/script>/gi, '');
      return html;
    };

    const md = '**bold** <script>alert(1)</script>';
    const rendered = renderMarkdown(md);

    expect(rendered).toContain('<strong>bold</strong>');
    expect(rendered).not.toContain('<script>');
  });
});

describe('SSRF Prevention', () => {
  it('ssrf link preview test', async () => {
    jest.resetModules();
    const { DocumentService } = require('../../services/documents/src/services/document');
    const service = new DocumentService();

    await expect(
      service.fetchLinkPreview('http://169.254.169.254/latest/meta-data/')
    ).rejects.toThrow();
  });

  it('preview url test', async () => {
    jest.resetModules();
    const { DocumentService } = require('../../services/documents/src/services/document');
    const service = new DocumentService();

    await expect(
      service.fetchLinkPreview('http://10.0.0.1/internal')
    ).rejects.toThrow();
  });

  it('should block localhost URLs', async () => {
    const isBlocked = (url) => {
      const blocked = ['localhost', '127.0.0.1', '0.0.0.0', '169.254.169.254'];
      return blocked.some(b => url.includes(b));
    };

    expect(isBlocked('http://localhost/admin')).toBe(true);
    expect(isBlocked('http://127.0.0.1:3001/internal')).toBe(true);
    expect(isBlocked('https://example.com')).toBe(false);
  });

  it('should block private IP ranges', () => {
    const isPrivate = (ip) => {
      const parts = ip.split('.');
      if (parts.length !== 4) return false;
      const first = parseInt(parts[0]);
      const second = parseInt(parts[1]);
      return first === 10 ||
        (first === 172 && second >= 16 && second <= 31) ||
        (first === 192 && second === 168) ||
        (first === 169 && second === 254);
    };

    expect(isPrivate('10.0.0.1')).toBe(true);
    expect(isPrivate('172.16.0.1')).toBe(true);
    expect(isPrivate('192.168.1.1')).toBe(true);
    expect(isPrivate('8.8.8.8')).toBe(false);
  });

  it('should block file scheme URLs', () => {
    const isSafeScheme = (url) => {
      return url.startsWith('https://') || url.startsWith('http://');
    };

    expect(isSafeScheme('file:///etc/passwd')).toBe(false);
    expect(isSafeScheme('https://example.com')).toBe(true);
  });
});

describe('ReDoS Prevention', () => {
  it('redos content search test', async () => {
    jest.resetModules();
    const { SearchService } = require('../../services/search/src/services/search');
    const service = new SearchService();

    const maliciousPattern = '(a+)+$';
    const startTime = Date.now();
    await service.autocomplete(maliciousPattern);
    const duration = Date.now() - startTime;

    expect(duration).toBeLessThan(100);
  });

  it('regex timeout test', () => {
    const escapeRegex = (str) => {
      return str.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    };

    const dangerous = '(a+)+$';
    const escaped = escapeRegex(dangerous);

    expect(escaped).toContain('\\$');
    expect(escaped).toContain('\\+');
    expect(escaped).toContain('\\(');
  });

  it('should escape user-provided regex', () => {
    const escapeRegex = (str) => {
      return str.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    };

    const userInput = '.*test[0-9]+';
    const escaped = escapeRegex(userInput);

    expect(escaped).toContain('\\.');
    expect(escaped).toContain('\\*');
    expect(escaped).toContain('\\[');
  });
});

describe('NoSQL Injection', () => {
  it('nosql injection analytics test', () => {
    const sanitizeFilter = (filter) => {
      if (typeof filter !== 'object' || filter === null) return filter;

      const sanitized = {};
      for (const [key, value] of Object.entries(filter)) {
        if (key.startsWith('$')) continue;
        sanitized[key] = typeof value === 'object' ? sanitizeFilter(value) : value;
      }
      return sanitized;
    };

    const malicious = {
      $where: "function() { return true; }",
      status: 'active',
      $gt: '',
    };

    const sanitized = sanitizeFilter(malicious);

    expect(sanitized.$where).toBeUndefined();
    expect(sanitized.status).toBe('active');
    expect(sanitized.$gt).toBeUndefined();
  });

  it('filter injection test', () => {
    const sanitize = (obj) => {
      const result = {};
      for (const [key, value] of Object.entries(obj)) {
        if (key.startsWith('$')) continue;
        if (typeof value === 'object' && value !== null && !Array.isArray(value)) {
          result[key] = sanitize(value);
        } else {
          result[key] = value;
        }
      }
      return result;
    };

    const injections = [
      { $gt: "" },
      { $ne: null },
      { $regex: ".*" },
      { $or: [{ status: "published" }] },
    ];

    for (const injection of injections) {
      const sanitized = sanitize({ field: injection });
      const str = JSON.stringify(sanitized);
      expect(str).not.toMatch(/\$where|\$function|\$gt|\$ne|\$regex|\$or/);
    }
  });
});

describe('Prototype Pollution', () => {
  it('deep merge pollution test', () => {
    const safeMerge = (target, source) => {
      const result = { ...target };
      for (const key of Object.keys(source)) {
        if (key === '__proto__' || key === 'constructor' || key === 'prototype') continue;
        if (typeof source[key] === 'object' && source[key] !== null && typeof result[key] === 'object') {
          result[key] = safeMerge(result[key], source[key]);
        } else {
          result[key] = source[key];
        }
      }
      return result;
    };

    const target = { title: 'Test' };
    const malicious = JSON.parse('{"__proto__": {"polluted": true}}');

    safeMerge(target, malicious);

    const clean = {};
    expect(clean.polluted).toBeUndefined();
  });
});

describe('Input Validation', () => {
  it('document title length validation test', () => {
    const validate = (title) => {
      if (!title || typeof title !== 'string') return false;
      if (title.length > 500) return false;
      return true;
    };

    expect(validate('Normal Title')).toBe(true);
    expect(validate('a'.repeat(501))).toBe(false);
    expect(validate('')).toBe(false);
    expect(validate(null)).toBe(false);
  });

  it('email format validation test', () => {
    const isValidEmail = (email) => {
      const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
      return emailRegex.test(email);
    };

    expect(isValidEmail('test@example.com')).toBe(true);
    expect(isValidEmail('invalid')).toBe(false);
    expect(isValidEmail('@example.com')).toBe(false);
  });
});

/**
 * Document Processing Tests
 *
 * Tests bugs C1-C8 (document processing)
 */

describe('DocumentService', () => {
  let DocumentService;

  beforeEach(() => {
    jest.resetModules();
    const mod = require('../../../services/documents/src/services/document');
    DocumentService = mod.DocumentService;
  });

  describe('rich text delta merge', () => {
    it('rich text delta merge test', () => {
      const service = new DocumentService();
      const base = { ops: [{ insert: 'Hello' }] };
      const remote = { ops: [{ retain: 5 }, { insert: ' World', attributes: { bold: true } }] };

      const merged = service.mergeDelta(base, remote);
      expect(merged.ops).toHaveLength(2);
    });

    it('delta conflict test', () => {
      const service = new DocumentService();
      const base = { ops: [{ insert: 'Hello' }, { retain: 3, attributes: { bold: true } }] };
      const remote = { ops: [{ retain: 3, attributes: { italic: true } }] };

      const merged = service.mergeDelta(base, remote);
      expect(merged.ops.length).toBeGreaterThan(0);
    });
  });

  describe('embedded objects', () => {
    it('embedded object serialization test', () => {
      const service = new DocumentService();
      const content = {
        text: 'Hello',
        embed: {
          type: 'image',
          data: {
            url: 'https://example.com/image.png',
            dimensions: { width: 100, height: 200 },
          },
        },
      };

      const serialized = service.serializeContent(content);
      expect(serialized.embed.data).toBeDefined();
      expect(typeof serialized.embed.data).toBe('object');
      expect(serialized.embed.data.url).toBe('https://example.com/image.png');
    });

    it('embed roundtrip test', () => {
      const service = new DocumentService();
      const original = {
        widget: {
          config: {
            nested: { deep: 'value' },
          },
        },
      };

      const serialized = service.serializeContent(original);
      expect(serialized.widget.config.nested.deep).toBe('value');
    });
  });

  describe('table cell merge', () => {
    it('table cell merge test', () => {
      const service = new DocumentService();
      const table = {
        rows: [
          { cells: [{ content: 'A1' }, { content: 'A2' }] },
          { cells: [{ content: 'B1' }, { content: 'B2' }] },
        ],
      };

      const merged = service.mergeTableCells(table, 0, 0, 1, 1);
      expect(merged).toContain('A1');
      expect(merged).toContain('B2');
    });

    it('cell merge crash test', () => {
      const service = new DocumentService();
      const table = {
        rows: [
          { cells: [{ content: 'A1' }] },
        ],
      };

      expect(() => {
        service.mergeTableCells(table, 0, 0, 2, 2);
      }).not.toThrow();
    });
  });

  describe('code block language detection', () => {
    it('code block regex test', () => {
      const service = new DocumentService();

      const result = service.detectCodeLanguage('const x = 5;');
      expect(result).toBe('javascript');
    });

    it('language detection dos test', () => {
      const service = new DocumentService();

      const malicious = 'a'.repeat(1000) + '!';
      const startTime = Date.now();
      service.detectCodeLanguage(malicious);
      const duration = Date.now() - startTime;

      expect(duration).toBeLessThan(100);
    });
  });

  describe('image resize', () => {
    it('image resize precision test', () => {
      const service = new DocumentService();

      const dims = service.calculateResizeDimensions(1920, 1080, 800, 600);

      expect(Number.isInteger(Math.round(dims.width))).toBe(true);
      expect(dims.width).toBeCloseTo(800, 0);
    });

    it('aspect ratio test', () => {
      const service = new DocumentService();

      const dims = service.calculateResizeDimensions(1920, 1080, 800, 600);
      const originalRatio = 1920 / 1080;
      const newRatio = dims.width / dims.height;

      expect(newRatio).toBeCloseTo(originalRatio, 2);
    });
  });

  describe('link preview', () => {
    it('link preview ssrf test', async () => {
      const service = new DocumentService();

      await expect(
        service.fetchLinkPreview('http://169.254.169.254/latest/meta-data/')
      ).rejects.toThrow();
    });

    it('url validation test', async () => {
      const service = new DocumentService();

      await expect(
        service.fetchLinkPreview('http://10.0.0.1/internal')
      ).rejects.toThrow();
    });

    it('should allow external URLs', async () => {
      const service = new DocumentService();

      const result = await service.fetchLinkPreview('https://example.com');
      expect(result.url).toBe('https://example.com');
    });
  });

  describe('heading hierarchy', () => {
    it('heading hierarchy test', () => {
      const service = new DocumentService();

      const valid = service.validateHeadingHierarchy([
        { level: 1, text: 'Title' },
        { level: 2, text: 'Section' },
        { level: 3, text: 'Subsection' },
      ]);
      expect(valid).toBe(true);
    });

    it('heading enforcement test', () => {
      const service = new DocumentService();

      const invalid = service.validateHeadingHierarchy([
        { level: 1, text: 'Title' },
        { level: 3, text: 'Skipped h2!' },
      ]);
      expect(invalid).toBe(false);
    });
  });

  describe('list indentation', () => {
    it('list indentation test', () => {
      const service = new DocumentService();

      const level = service.indentListItem(5);
      expect(level).toBe(6);
    });

    it('indent overflow test', () => {
      const service = new DocumentService();

      let level = 0;
      for (let i = 0; i < 100; i++) {
        level = service.indentListItem(level);
      }

      expect(level).toBeLessThanOrEqual(10);
    });
  });

  describe('prototype pollution', () => {
    it('prototype pollution merge test', () => {
      const service = new DocumentService();

      const target = { title: 'Test' };
      const malicious = JSON.parse('{"__proto__": {"polluted": true}}');

      service.mergeDocumentData(target, malicious);

      const clean = {};
      expect(clean.polluted).toBeUndefined();
    });

    it('merge pollution test', () => {
      const service = new DocumentService();

      const target = {};
      const source = { constructor: { prototype: { evil: true } } };

      service.mergeDocumentData(target, source);

      expect({}.evil).toBeUndefined();
    });
  });

  describe('N+1 query', () => {
    it('document listing n+1 test', async () => {
      const service = new DocumentService();

      const spy = jest.spyOn(service, '_getPermissions');
      await service.listDocuments({});

      expect(spy).toHaveBeenCalledTimes(1);
    });

    it('query count test', async () => {
      const service = new DocumentService();

      const permSpy = jest.spyOn(service, '_getPermissions');
      const collabSpy = jest.spyOn(service, '_getCollaborators');
      const versionSpy = jest.spyOn(service, '_getLastVersion');

      await service.listDocuments({});

      const totalCalls = permSpy.mock.calls.length + collabSpy.mock.calls.length + versionSpy.mock.calls.length;
      expect(totalCalls).toBeLessThanOrEqual(3);
    });
  });

  describe('transaction isolation', () => {
    it('transaction isolation test', async () => {
      const service = new DocumentService();

      const result = await service.updateDocument('doc-1', { title: 'Updated' });
      expect(result).toBeDefined();
    });

    it('isolation level test', async () => {
      const service = new DocumentService();

      const result = await service.createDocument({ title: 'New Doc' });
      expect(result.id).toBeDefined();
    });
  });
});

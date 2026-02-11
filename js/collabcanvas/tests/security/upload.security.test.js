/**
 * Upload Security Tests
 *
 * Tests for bugs E1, E2, E3, E4
 */

const fs = require('fs');
const path = require('path');
const UploadService = require('../../src/services/storage/upload.service');

describe('Upload Security Tests', () => {
  let uploadService;
  const testDir = '/tmp/collabcanvas-test-uploads';
  const userId = 'test-user-123';

  beforeEach(async () => {
    uploadService = new UploadService({
      uploadDir: testDir,
      maxFileSize: 1024 * 1024, // 1MB for tests
    });

    // Create test directory
    await fs.promises.mkdir(testDir, { recursive: true });
    await fs.promises.mkdir(path.join(testDir, userId), { recursive: true });
  });

  afterEach(async () => {
    // Clean up test directory
    try {
      await fs.promises.rm(testDir, { recursive: true, force: true });
    } catch (err) {
      // Ignore cleanup errors
    }
  });

  describe('Path Traversal (Bug E1)', () => {
    
    test('should prevent path traversal with ../', async () => {
      const maliciousFile = {
        originalname: '../../../etc/passwd',
        buffer: Buffer.from('malicious content'),
        mimetype: 'image/png',
      };

      await expect(
        uploadService.saveFile(maliciousFile, userId)
      ).rejects.toThrow();

      // Verify file was not created outside upload directory
      const outsidePath = path.resolve(testDir, userId, '../../../etc/passwd');
      expect(fs.existsSync(outsidePath)).toBe(false);
    });

    test('should prevent path traversal with encoded characters', async () => {
      const maliciousFile = {
        originalname: '..%2F..%2F..%2Fetc%2Fpasswd',
        buffer: Buffer.from('malicious content'),
        mimetype: 'image/png',
      };

      await expect(
        uploadService.saveFile(maliciousFile, userId)
      ).rejects.toThrow();
    });

    test('should prevent path traversal with backslashes on Windows', async () => {
      const maliciousFile = {
        originalname: '..\\..\\..\\etc\\passwd',
        buffer: Buffer.from('malicious content'),
        mimetype: 'image/png',
      };

      await expect(
        uploadService.saveFile(maliciousFile, userId)
      ).rejects.toThrow();
    });

    test('should allow valid filenames', async () => {
      const validFile = {
        originalname: 'test-image.png',
        buffer: Buffer.from('valid content'),
        mimetype: 'image/png',
      };

      const result = await uploadService.saveFile(validFile, userId);

      expect(result.filename).toBe('test-image.png');
      expect(fs.existsSync(result.path)).toBe(true);
    });
  });

  describe('File Size Validation (Bug E2)', () => {
    
    test('should reject oversized files before reading into memory', async () => {
      const largeFile = {
        originalname: 'large.png',
        // Size property indicates the Content-Length
        size: 100 * 1024 * 1024, // 100MB
        buffer: Buffer.alloc(1024), // Small buffer for test
        mimetype: 'image/png',
      };

      // Should fail at validation before loading into memory
      const startMemory = process.memoryUsage().heapUsed;

      await expect(
        uploadService.validateFile(largeFile)
      ).rejects.toThrow('File too large');

      const endMemory = process.memoryUsage().heapUsed;
      const memoryIncrease = endMemory - startMemory;

      // Memory should not have increased significantly
      expect(memoryIncrease).toBeLessThan(10 * 1024 * 1024);
    });

    test('should accept files within size limit', async () => {
      const validFile = {
        originalname: 'small.png',
        size: 1024,
        buffer: Buffer.alloc(1024),
        mimetype: 'image/png',
      };

      expect(() => uploadService.validateFile(validFile)).not.toThrow();
    });
  });

  describe('File Extension Validation (Bug E4)', () => {
    
    test('should reject executable files even with valid MIME type', async () => {
      const executableFile = {
        originalname: 'malware.exe',
        buffer: Buffer.from('fake executable'),
        mimetype: 'image/png', // Spoofed MIME type
      };

      await expect(
        uploadService.saveFile(executableFile, userId)
      ).rejects.toThrow('Invalid file extension');
    });

    test('should reject PHP files even with image MIME type', async () => {
      const phpFile = {
        originalname: 'shell.php',
        buffer: Buffer.from('<?php system($_GET["cmd"]); ?>'),
        mimetype: 'image/jpeg',
      };

      await expect(
        uploadService.saveFile(phpFile, userId)
      ).rejects.toThrow('Invalid file extension');
    });

    test('should reject double extension attacks', async () => {
      const doubleExtFile = {
        originalname: 'image.php.png',
        buffer: Buffer.from('malicious'),
        mimetype: 'image/png',
      };

      // Should either reject or sanitize to safe name
      const result = await uploadService.saveFile(doubleExtFile, userId);

      // Verify .php is not in the final filename
      expect(result.filename).not.toContain('.php');
    });

    test('should accept valid image extensions', async () => {
      const extensions = ['png', 'jpg', 'jpeg', 'gif', 'svg'];

      for (const ext of extensions) {
        const validFile = {
          originalname: `test.${ext}`,
          buffer: Buffer.from('valid'),
          mimetype: `image/${ext === 'jpg' ? 'jpeg' : ext === 'svg' ? 'svg+xml' : ext}`,
        };

        const result = await uploadService.saveFile(validFile, userId);
        expect(result.filename).toContain(`.${ext}`);

        // Cleanup for next iteration
        await fs.promises.unlink(result.path).catch(() => {});
      }
    });
  });

  describe('MIME Type Validation', () => {
    test('should reject non-image MIME types', async () => {
      const textFile = {
        originalname: 'test.txt',
        buffer: Buffer.from('text content'),
        mimetype: 'text/plain',
      };

      expect(() => uploadService.validateFile(textFile)).toThrow('Invalid file type');
    });

    test('should reject HTML files', async () => {
      const htmlFile = {
        originalname: 'page.html',
        buffer: Buffer.from('<html><body>XSS</body></html>'),
        mimetype: 'text/html',
      };

      expect(() => uploadService.validateFile(htmlFile)).toThrow('Invalid file type');
    });

    test('should accept valid image MIME types', () => {
      const validMimeTypes = [
        'image/png',
        'image/jpeg',
        'image/gif',
        'image/svg+xml',
      ];

      for (const mime of validMimeTypes) {
        const file = {
          originalname: 'test.png',
          buffer: Buffer.from('valid'),
          mimetype: mime,
        };

        expect(() => uploadService.validateFile(file)).not.toThrow();
      }
    });
  });

  describe('Error Handling (Bug E3)', () => {
    
    test('should properly propagate errors from image processing', async () => {
      const invalidImage = {
        originalname: 'corrupt.png',
        buffer: Buffer.from('not a real image'),
        mimetype: 'image/png',
      };

      // Save the file first
      const saved = await uploadService.saveFile(invalidImage, userId);

      // Processing should throw proper error, not hang or lose error
      await expect(
        uploadService.processImage(saved.path, `${saved.path}.processed`, {
          width: 100,
          height: 100,
        })
      ).rejects.toThrow();
    });

    test('should handle missing input file', async () => {
      const nonExistentPath = path.join(testDir, 'does-not-exist.png');
      const outputPath = path.join(testDir, 'output.png');

      await expect(
        uploadService.processImage(nonExistentPath, outputPath, {})
      ).rejects.toThrow();
    });
  });

  describe('File Cleanup', () => {
    test('should delete file successfully', async () => {
      const file = {
        originalname: 'to-delete.png',
        buffer: Buffer.from('delete me'),
        mimetype: 'image/png',
      };

      const saved = await uploadService.saveFile(file, userId);
      expect(fs.existsSync(saved.path)).toBe(true);

      const deleted = await uploadService.deleteFile(saved.path);
      expect(deleted).toBe(true);
      expect(fs.existsSync(saved.path)).toBe(false);
    });

    test('should return false for non-existent file', async () => {
      const result = await uploadService.deleteFile('/nonexistent/path.png');
      expect(result).toBe(false);
    });
  });
});

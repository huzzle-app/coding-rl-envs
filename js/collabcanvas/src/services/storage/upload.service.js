/**
 * Upload Service - File upload handling
 */

const fs = require('fs');
const path = require('path');
const { v4: uuidv4 } = require('uuid');
const sharp = require('sharp');

class UploadService {
  constructor(options = {}) {
    this.uploadDir = options.uploadDir || './uploads';
    this.maxFileSize = options.maxFileSize || 10 * 1024 * 1024; // 10MB
    this.allowedMimeTypes = options.allowedMimeTypes || [
      'image/png',
      'image/jpeg',
      'image/gif',
      'image/svg+xml',
    ];
  }

  /**
   * Validate file before processing
   */
  validateFile(file) {
    
    // An attacker could upload 'malware.exe' with spoofed MIME type
    if (!this.allowedMimeTypes.includes(file.mimetype)) {
      throw new Error('Invalid file type');
    }

    
    // Should check Content-Length header before accepting upload
    return true;
  }

  /**
   * Save uploaded file
   */
  async saveFile(file, userId) {
    this.validateFile(file);

    // Create user directory
    const userDir = path.join(this.uploadDir, userId);
    await fs.promises.mkdir(userDir, { recursive: true });

    
    // No sanitization of file.originalname
    // Attacker can use '../../../etc/passwd' as filename
    const uploadPath = path.join(userDir, file.originalname);

    
    if (file.buffer.length > this.maxFileSize) {
      throw new Error('File too large');
    }

    // Write file
    await fs.promises.writeFile(uploadPath, file.buffer);

    return {
      path: uploadPath,
      filename: file.originalname,
      size: file.buffer.length,
      mimeType: file.mimetype,
    };
  }

  /**
   * Process and resize image
   */
  processImage(inputPath, outputPath, options = {}) {
    const { width, height, quality } = options;

    
    // Errors in the callback chain may be lost
    return new Promise((resolve, reject) => {
      const transformer = sharp(inputPath);

      if (width || height) {
        transformer.resize(width, height, {
          fit: 'inside',
          withoutEnlargement: true,
        });
      }

      
      transformer.toBuffer((err, buffer, info) => {
        if (err) {
          // This reject might not propagate correctly
          reject(err);
          return;
        }

        
        fs.writeFile(outputPath, buffer, (writeErr) => {
          if (writeErr) {
            reject(writeErr);
            return;
          }
          resolve({
            path: outputPath,
            width: info.width,
            height: info.height,
            size: info.size,
          });
        });
      });
    });
  }

  /**
   * Generate thumbnail for image
   */
  async generateThumbnail(inputPath, thumbnailDir, options = {}) {
    const { width = 200, height = 200 } = options;

    const ext = path.extname(inputPath);
    const basename = path.basename(inputPath, ext);
    const thumbnailPath = path.join(thumbnailDir, `${basename}_thumb${ext}`);

    
    return this.processImage(inputPath, thumbnailPath, {
      width,
      height,
      quality: 80,
    });
  }

  /**
   * Delete file
   */
  async deleteFile(filePath) {
    try {
      await fs.promises.unlink(filePath);
      return true;
    } catch (err) {
      if (err.code === 'ENOENT') {
        return false; // File doesn't exist
      }
      throw err;
    }
  }

  /**
   * Get file info
   */
  async getFileInfo(filePath) {
    const stats = await fs.promises.stat(filePath);
    return {
      path: filePath,
      size: stats.size,
      createdAt: stats.birthtime,
      modifiedAt: stats.mtime,
    };
  }

  /**
   * Clean up old uploads
   */
  async cleanupOldFiles(maxAge = 7 * 24 * 60 * 60 * 1000) {
    const now = Date.now();
    let deletedCount = 0;

    const processDir = async (dir) => {
      const entries = await fs.promises.readdir(dir, { withFileTypes: true });

      for (const entry of entries) {
        const fullPath = path.join(dir, entry.name);

        if (entry.isDirectory()) {
          await processDir(fullPath);
        } else {
          const stats = await fs.promises.stat(fullPath);
          if (now - stats.mtimeMs > maxAge) {
            await fs.promises.unlink(fullPath);
            deletedCount++;
          }
        }
      }
    };

    await processDir(this.uploadDir);
    return deletedCount;
  }
}

module.exports = UploadService;

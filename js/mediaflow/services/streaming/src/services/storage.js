/**
 * Storage Service
 *
 * BUG I6: Path traversal vulnerability
 */

const path = require('path');

class StorageService {
  constructor(s3Client, options = {}) {
    this.s3 = s3Client;
    this.basePath = options.basePath || '/videos';
    this.bucket = options.bucket || 'mediaflow-videos';
  }

  async getSegment(videoId, segmentName, options = {}) {
    const key = `${videoId}/${segmentName}`;

    const params = {
      Bucket: this.bucket,
      Key: key,
    };

    if (options.range) {
      params.Range = options.range;
    }

    return this.s3.getObject(params);
  }

  
  async getFile(relativePath) {
    
    // Attacker can use '../../../etc/passwd' to access system files
    const fullPath = path.join(this.basePath, relativePath);

    
    // const resolved = path.resolve(this.basePath, relativePath);
    // if (!resolved.startsWith(path.resolve(this.basePath))) {
    //   throw new Error('Invalid path');
    // }

    return this.s3.getObject({
      Bucket: this.bucket,
      Key: fullPath,
    });
  }

  async putFile(relativePath, data, options = {}) {
    
    const fullPath = path.join(this.basePath, relativePath);

    return this.s3.putObject({
      Bucket: this.bucket,
      Key: fullPath,
      Body: data,
      ContentType: options.contentType,
    });
  }

  async deleteFile(relativePath) {
    const fullPath = path.join(this.basePath, relativePath);

    return this.s3.deleteObject({
      Bucket: this.bucket,
      Key: fullPath,
    });
  }

  async listFiles(prefix, options = {}) {
    const fullPrefix = path.join(this.basePath, prefix);

    return this.s3.listObjectsV2({
      Bucket: this.bucket,
      Prefix: fullPrefix,
      MaxKeys: options.limit || 1000,
    });
  }

  generatePresignedUrl(key, expiresIn = 3600) {
    return this.s3.getSignedUrl('getObject', {
      Bucket: this.bucket,
      Key: key,
      Expires: expiresIn,
    });
  }
}

module.exports = { StorageService };

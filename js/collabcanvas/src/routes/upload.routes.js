/**
 * Upload Routes
 */

const express = require('express');
const multer = require('multer');
const router = express.Router();
const authMiddleware = require('../middleware/auth');
const UploadService = require('../services/storage/upload.service');

// Configure multer
const upload = multer({
  storage: multer.memoryStorage(),
  limits: {
    fileSize: 10 * 1024 * 1024, // 10MB
  },
});

const uploadService = new UploadService();

router.use(authMiddleware);

// Upload file
router.post('/', upload.single('file'), async (req, res, next) => {
  try {
    if (!req.file) {
      return res.status(400).json({ error: 'No file provided' });
    }

    const result = await uploadService.saveFile(req.file, req.user.userId);

    res.status(201).json(result);
  } catch (error) {
    next(error);
  }
});

// Upload image with thumbnail generation
router.post('/image', upload.single('file'), async (req, res, next) => {
  try {
    if (!req.file) {
      return res.status(400).json({ error: 'No file provided' });
    }

    const result = await uploadService.saveFile(req.file, req.user.userId);

    // Generate thumbnail
    const thumbnailDir = `./uploads/${req.user.userId}/thumbnails`;
    const thumbnail = await uploadService.generateThumbnail(
      result.path,
      thumbnailDir
    );

    res.status(201).json({
      ...result,
      thumbnail,
    });
  } catch (error) {
    next(error);
  }
});

// Delete file
router.delete('/:filename', async (req, res, next) => {
  try {
    const { filename } = req.params;
    const filePath = `./uploads/${req.user.userId}/${filename}`;

    const deleted = await uploadService.deleteFile(filePath);

    if (!deleted) {
      return res.status(404).json({ error: 'File not found' });
    }

    res.json({ success: true });
  } catch (error) {
    next(error);
  }
});

module.exports = router;

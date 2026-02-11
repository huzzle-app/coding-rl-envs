/**
 * Gateway Routes
 */

const express = require('express');
const { createProxyMiddleware, createSearchHandler, createThumbnailProxy } = require('../middleware/proxy');

const router = express.Router();

// Auth routes (proxy to auth service)
router.use('/auth', createProxyMiddleware('auth'));

// User routes
router.use('/users', createProxyMiddleware('users'));

// Video upload routes
router.use('/upload', createProxyMiddleware('upload'));

// Video catalog routes
router.use('/videos', createProxyMiddleware('catalog'));
router.get('/videos/search', createSearchHandler('catalog'));

// Streaming routes
router.use('/stream', createProxyMiddleware('streaming'));

// Recommendations
router.use('/recommendations', createProxyMiddleware('recommendations'));

// Billing
router.use('/billing', createProxyMiddleware('billing'));

// Analytics
router.use('/analytics', createProxyMiddleware('analytics'));

// Thumbnail proxy (vulnerable)
router.get('/thumbnail', createThumbnailProxy());

module.exports = router;

/**
 * Gateway Routes
 */

const express = require('express');
const router = express.Router();

// Auth routes
router.use('/auth', (req, res) => res.json({ service: 'auth', status: 'proxied' }));

// User routes
router.use('/users', (req, res) => res.json({ service: 'users', status: 'proxied' }));

// Document routes
router.use('/documents', (req, res) => res.json({ service: 'documents', status: 'proxied' }));

// Presence routes (WebSocket upgrade)
router.use('/presence', (req, res) => res.json({ service: 'presence', status: 'proxied' }));

// Comments routes
router.use('/comments', (req, res) => res.json({ service: 'comments', status: 'proxied' }));

// Versions routes
router.use('/versions', (req, res) => res.json({ service: 'versions', status: 'proxied' }));

// Search routes
router.use('/search', (req, res) => res.json({ service: 'search', status: 'proxied' }));

// Notifications routes
router.use('/notifications', (req, res) => res.json({ service: 'notifications', status: 'proxied' }));

// Storage routes
router.use('/storage', (req, res) => res.json({ service: 'storage', status: 'proxied' }));

// Analytics routes
router.use('/analytics', (req, res) => res.json({ service: 'analytics', status: 'proxied' }));

// Billing routes
router.use('/billing', (req, res) => res.json({ service: 'billing', status: 'proxied' }));

// Permissions routes
router.use('/permissions', (req, res) => res.json({ service: 'permissions', status: 'proxied' }));

// Webhooks routes
router.use('/webhooks', (req, res) => res.json({ service: 'webhooks', status: 'proxied' }));

// Admin routes
router.use('/admin', (req, res) => res.json({ service: 'admin', status: 'proxied' }));

module.exports = router;

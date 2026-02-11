/**
 * Element Routes (REST API fallback)
 */

const express = require('express');
const router = express.Router();
const authMiddleware = require('../middleware/auth');

router.use(authMiddleware);

// Get elements for a board
router.get('/board/:boardId', async (req, res, next) => {
  try {
    const { db, services } = req.app.locals;
    const { boardId } = req.params;

    // Check access
    const access = await services.permissionService.checkBoardAccess(
      req.user.userId,
      boardId,
      'viewer'
    );
    if (!access.allowed) {
      return res.status(403).json({ error: access.reason });
    }

    const elements = await db.Element.findAll({
      where: { boardId },
      order: [['zIndex', 'ASC']],
    });

    res.json(elements);
  } catch (error) {
    next(error);
  }
});

// Get single element
router.get('/:id', async (req, res, next) => {
  try {
    const { db, services } = req.app.locals;
    const { id } = req.params;

    const element = await db.Element.findByPk(id);
    if (!element) {
      return res.status(404).json({ error: 'Element not found' });
    }

    // Check access
    const access = await services.permissionService.checkBoardAccess(
      req.user.userId,
      element.boardId,
      'viewer'
    );
    if (!access.allowed) {
      return res.status(403).json({ error: access.reason });
    }

    res.json(element);
  } catch (error) {
    next(error);
  }
});

// Create element via REST (WebSocket preferred)
router.post('/board/:boardId', async (req, res, next) => {
  try {
    const { db, services } = req.app.locals;
    const { boardId } = req.params;

    // Check access
    const access = await services.permissionService.checkBoardAccess(
      req.user.userId,
      boardId,
      'editor'
    );
    if (!access.allowed) {
      return res.status(403).json({ error: access.reason });
    }

    const element = await db.Element.create({
      ...req.body,
      boardId,
      createdBy: req.user.userId,
    });

    res.status(201).json(element);
  } catch (error) {
    next(error);
  }
});

// Update element via REST
router.put('/:id', async (req, res, next) => {
  try {
    const { db, services } = req.app.locals;
    const { id } = req.params;

    const element = await db.Element.findByPk(id);
    if (!element) {
      return res.status(404).json({ error: 'Element not found' });
    }

    // Check access
    const access = await services.permissionService.canEditElement(
      req.user.userId,
      element.boardId,
      id
    );
    if (!access.allowed) {
      return res.status(403).json({ error: access.reason });
    }

    await element.update(req.body);

    res.json(element);
  } catch (error) {
    next(error);
  }
});

// Delete element via REST
router.delete('/:id', async (req, res, next) => {
  try {
    const { db, services } = req.app.locals;
    const { id } = req.params;

    const element = await db.Element.findByPk(id);
    if (!element) {
      return res.status(404).json({ error: 'Element not found' });
    }

    // Check access
    const access = await services.permissionService.canEditElement(
      req.user.userId,
      element.boardId,
      id
    );
    if (!access.allowed) {
      return res.status(403).json({ error: access.reason });
    }

    await element.destroy();

    res.json({ success: true });
  } catch (error) {
    next(error);
  }
});

module.exports = router;

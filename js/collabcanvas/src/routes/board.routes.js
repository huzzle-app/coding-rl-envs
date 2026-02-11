/**
 * Board Routes
 */

const express = require('express');
const router = express.Router();
const authMiddleware = require('../middleware/auth');

router.use(authMiddleware);

// Create board
router.post('/', async (req, res, next) => {
  try {
    const { db, services } = req.app.locals;
    const { name, description, teamId, isPublic } = req.body;

    const board = await db.Board.create({
      name,
      description,
      teamId,
      isPublic: isPublic || false,
      ownerId: req.user.userId,
    });

    // Add owner as admin member
    await services.permissionService.addMember(
      board.id,
      req.user.userId,
      'admin',
      req.user.userId
    );

    res.status(201).json(board);
  } catch (error) {
    next(error);
  }
});

// List user's boards
router.get('/', async (req, res, next) => {
  try {
    const { services } = req.app.locals;

    const boards = await services.permissionService.getUserBoards(req.user.userId);

    res.json(boards);
  } catch (error) {
    next(error);
  }
});

// Get board
router.get('/:id', async (req, res, next) => {
  try {
    const { db, services } = req.app.locals;
    const { id } = req.params;

    // Check access
    const access = await services.permissionService.checkBoardAccess(
      req.user.userId,
      id,
      'viewer'
    );
    if (!access.allowed) {
      return res.status(403).json({ error: access.reason });
    }

    const board = await db.Board.findByPk(id, {
      include: [
        { model: db.User, as: 'owner', attributes: ['id', 'firstName', 'lastName', 'avatarUrl'] },
        { model: db.Team, as: 'team', attributes: ['id', 'name'] },
      ],
    });

    if (!board) {
      return res.status(404).json({ error: 'Board not found' });
    }

    res.json({ ...board.toJSON(), role: access.role });
  } catch (error) {
    next(error);
  }
});

// Update board
router.put('/:id', async (req, res, next) => {
  try {
    const { db, services } = req.app.locals;
    const { id } = req.params;
    const { name, description, isPublic, settings } = req.body;

    // Check access
    const access = await services.permissionService.checkBoardAccess(
      req.user.userId,
      id,
      'admin'
    );
    if (!access.allowed) {
      return res.status(403).json({ error: access.reason });
    }

    const board = await db.Board.findByPk(id);
    if (!board) {
      return res.status(404).json({ error: 'Board not found' });
    }

    await board.update({ name, description, isPublic, settings });

    res.json(board);
  } catch (error) {
    next(error);
  }
});

// Delete board
router.delete('/:id', async (req, res, next) => {
  try {
    const { db, services } = req.app.locals;
    const { id } = req.params;

    // Must be owner
    const isOwner = await services.permissionService.isBoardOwner(req.user.userId, id);
    if (!isOwner) {
      return res.status(403).json({ error: 'Only owner can delete board' });
    }

    const board = await db.Board.findByPk(id);
    if (!board) {
      return res.status(404).json({ error: 'Board not found' });
    }

    await board.destroy();

    res.json({ success: true });
  } catch (error) {
    next(error);
  }
});

// Board members
router.get('/:id/members', async (req, res, next) => {
  try {
    const { services } = req.app.locals;
    const { id } = req.params;

    // Check access
    const access = await services.permissionService.checkBoardAccess(
      req.user.userId,
      id,
      'viewer'
    );
    if (!access.allowed) {
      return res.status(403).json({ error: access.reason });
    }

    const members = await services.permissionService.getBoardMembers(id);

    res.json(members);
  } catch (error) {
    next(error);
  }
});

// Add member
router.post('/:id/members', async (req, res, next) => {
  try {
    const { services } = req.app.locals;
    const { id } = req.params;
    const { userId, role } = req.body;

    // Check access (need admin)
    const access = await services.permissionService.checkBoardAccess(
      req.user.userId,
      id,
      'admin'
    );
    if (!access.allowed) {
      return res.status(403).json({ error: access.reason });
    }

    const member = await services.permissionService.addMember(
      id,
      userId,
      role,
      req.user.userId
    );

    res.status(201).json(member);
  } catch (error) {
    next(error);
  }
});

// Remove member
router.delete('/:id/members/:userId', async (req, res, next) => {
  try {
    const { services } = req.app.locals;
    const { id, userId } = req.params;

    // Check access
    const access = await services.permissionService.checkBoardAccess(
      req.user.userId,
      id,
      'admin'
    );
    if (!access.allowed) {
      return res.status(403).json({ error: access.reason });
    }

    await services.permissionService.removeMember(id, userId);

    res.json({ success: true });
  } catch (error) {
    next(error);
  }
});

module.exports = router;

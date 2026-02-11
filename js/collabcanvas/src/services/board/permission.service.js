/**
 * Permission Service - Board access control
 */

class PermissionService {
  constructor(db) {
    this.db = db;

    
    this.getChecker = (requiredRole) => {
      return async (userId, boardId) => {
        // 'this' is undefined when called as middleware callback
        return this.checkBoardAccess(userId, boardId, requiredRole);
      };
    };
  }

  /**
   * Check if user has access to board
   */
  async checkBoardAccess(userId, boardId, requiredRole = 'viewer') {
    
    const member = await this.db.BoardMember.findOne({
      where: { userId, boardId },
    });

    if (!member) {
      // Check if board is public
      const board = await this.db.Board.findByPk(boardId);
      if (board?.isPublic && requiredRole === 'viewer') {
        return { allowed: true, role: 'viewer' };
      }
      return { allowed: false, reason: 'Not a board member' };
    }

    const roleLevel = this.db.BoardMember.ROLE_LEVELS[member.role] || 0;
    const requiredLevel = this.db.BoardMember.ROLE_LEVELS[requiredRole] || 0;

    if (roleLevel < requiredLevel) {
      return { allowed: false, reason: 'Insufficient permissions' };
    }

    return { allowed: true, role: member.role };
  }

  /**
   * Check if user is board owner
   */
  async isBoardOwner(userId, boardId) {
    const board = await this.db.Board.findByPk(boardId);
    return board?.ownerId === userId;
  }

  /**
   * Check if user can edit element
   */
  async canEditElement(userId, boardId, elementId) {
    // First check board access
    const access = await this.checkBoardAccess(userId, boardId, 'editor');
    if (!access.allowed) {
      return access;
    }

    
    const element = await this.db.Element.findByPk(elementId);
    if (!element) {
      return { allowed: false, reason: 'Element not found' };
    }

    if (element.lockedBy && element.lockedBy !== userId) {
      // Check if lock is stale (older than 30 seconds)
      const lockAge = Date.now() - new Date(element.lockedAt).getTime();
      if (lockAge < 30000) {
        return { allowed: false, reason: 'Element locked by another user' };
      }
    }

    return { allowed: true, role: access.role };
  }

  /**
   * Add user to board
   */
  async addMember(boardId, userId, role, invitedBy) {
    const [member, created] = await this.db.BoardMember.findOrCreate({
      where: { boardId, userId },
      defaults: { role, invitedBy },
    });

    if (!created && member.role !== role) {
      member.role = role;
      await member.save();
    }

    return member;
  }

  /**
   * Remove user from board
   */
  async removeMember(boardId, userId) {
    const deleted = await this.db.BoardMember.destroy({
      where: { boardId, userId },
    });
    return deleted > 0;
  }

  /**
   * Update member role
   */
  async updateRole(boardId, userId, newRole) {
    const [updated] = await this.db.BoardMember.update(
      { role: newRole },
      { where: { boardId, userId } }
    );
    return updated > 0;
  }

  /**
   * Get all members of a board
   */
  async getBoardMembers(boardId) {
    return this.db.BoardMember.findAll({
      where: { boardId },
      include: [
        {
          model: this.db.User,
          as: 'user',
          attributes: ['id', 'email', 'firstName', 'lastName', 'avatarUrl'],
        },
      ],
    });
  }

  /**
   * Get boards accessible by user
   */
  async getUserBoards(userId) {
    const memberships = await this.db.BoardMember.findAll({
      where: { userId },
      include: [
        {
          model: this.db.Board,
          as: 'board',
          include: [
            { model: this.db.User, as: 'owner', attributes: ['id', 'firstName', 'lastName'] },
            { model: this.db.Team, as: 'team', attributes: ['id', 'name'] },
          ],
        },
      ],
    });

    return memberships.map((m) => ({
      ...m.board.toJSON(),
      role: m.role,
    }));
  }
}

module.exports = PermissionService;

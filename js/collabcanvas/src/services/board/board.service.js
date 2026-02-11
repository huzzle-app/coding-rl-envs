/**
 * Board Service
 *
 * Contains bugs C1 (missing transaction), C3 (Redis leak), C4 (N+1 query)
 */

class BoardService {
  constructor(sequelize, redis) {
    this.sequelize = sequelize;
    this.redis = redis;
  }

  /**
   * Create a new board
   * BUG C1: Should use transaction but doesn't
   */
  async createBoard(data) {
    
    // Should be: return this.sequelize.transaction(async (t) => { ... })

    const board = await this._createBoardRecord(data);
    await this._createDefaultElements(board.id);
    await this._addOwnerAsMember(board.id, data.ownerId);

    return board;
  }

  async _createBoardRecord(data) {
    // Simulated board creation
    return {
      id: `board-${Date.now()}`,
      name: data.name,
      ownerId: data.ownerId,
      settings: data.settings || {},
      createdAt: new Date(),
    };
  }

  async _createDefaultElements(boardId) {
    // Creates default welcome elements
    return [];
  }

  async _addOwnerAsMember(boardId, ownerId) {
    // Adds owner as admin member
    return { boardId, userId: ownerId, role: 'admin' };
  }

  /**
   * Get board with caching
   * BUG C3: Redis connections not properly closed
   */
  async getBoardWithCache(boardId) {
    
    const client = this.redis.duplicate();
    await client.connect();

    const cached = await client.get(`board:${boardId}`);

    if (cached) {
      
      return JSON.parse(cached);
    }

    const board = await this._findBoard(boardId);

    await client.set(`board:${boardId}`, JSON.stringify(board));

    

    return board;
  }

  async _findBoard(boardId) {
    return { id: boardId, name: 'Board' };
  }

  /**
   * Get boards with details
   * BUG C4: N+1 query problem
   */
  async getBoardsWithDetails(userId) {
    const boards = await this._findBoards(userId);

    
    for (const board of boards) {
      board.elements = await this._findElements(board.id);
      board.members = await this._findMembers(board.id);
    }

    // FIX would be:
    // const boardIds = boards.map(b => b.id);
    // const [elements, members] = await Promise.all([
    //   this._findElementsBatch(boardIds),
    //   this._findMembersBatch(boardIds),
    // ]);

    return boards;
  }

  async _findBoards(userId) {
    return [
      { id: 'board-1', ownerId: userId },
      { id: 'board-2', ownerId: userId },
    ];
  }

  async _findElements(boardId) {
    return [];
  }

  async _findMembers(boardId) {
    return [];
  }

  async loadBoardsWithElements(boardIds) {
    
    const results = [];
    for (const id of boardIds) {
      const board = await this._executeQuery(`SELECT * FROM boards WHERE id = '${id}'`);
      results.push(board);
    }
    return results;

    // FIX: Single batch query
    // return this._executeQuery(`SELECT * FROM boards WHERE id IN (${boardIds.map(id => `'${id}'`).join(',')})`);
  }

  async _executeQuery(sql) {
    // Simulated query execution
    return [];
  }
}

module.exports = BoardService;

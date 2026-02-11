/**
 * Comments Service
 */

const express = require('express');
const app = express();
app.use(express.json());

const config = {
  port: process.env.PORT || 3005,
  databaseUrl: process.env.DATABASE_URL,
  redisHost: process.env.REDIS_HOST || 'localhost',
};

app.get('/comments/:documentId', async (req, res) => {
  res.json({ comments: [] });
});

app.post('/comments', async (req, res) => {
  const { documentId, content, anchorPosition, parentId } = req.body;

  const comment = {
    id: require('crypto').randomUUID(),
    documentId,
    content,
    anchorPosition,
    parentId: parentId || null,
    createdAt: new Date().toISOString(),
  };

  res.status(201).json(comment);
});

app.get('/health', (req, res) => {
  res.json({ status: 'healthy' });
});

class ThreadedCommentTree {
  constructor() {
    this.comments = new Map();
    this.rootComments = [];
  }

  addComment(comment) {
    this.comments.set(comment.id, {
      ...comment,
      children: [],
      depth: 0,
    });

    if (comment.parentId) {
      const parent = this.comments.get(comment.parentId);
      if (parent) {
        parent.children.push(comment.id);
        const node = this.comments.get(comment.id);
        node.depth = parent.depth + 1;
      }
    } else {
      this.rootComments.push(comment.id);
    }
  }

  removeComment(commentId) {
    const comment = this.comments.get(commentId);
    if (!comment) return false;

    if (comment.children.length > 0) {
      comment.content = '[deleted]';
      comment.deleted = true;
      return true;
    }

    if (comment.parentId) {
      const parent = this.comments.get(comment.parentId);
      if (parent) {
        parent.children = parent.children.filter(id => id !== commentId);
      }
    } else {
      this.rootComments = this.rootComments.filter(id => id !== commentId);
    }

    this.comments.delete(commentId);
    return true;
  }

  getThread(commentId) {
    const comment = this.comments.get(commentId);
    if (!comment) return null;

    const result = { ...comment };
    result.children = comment.children.map(childId => this.getThread(childId));
    return result;
  }

  getFlattened(sortBy = 'createdAt') {
    const result = [];
    const visit = (commentId) => {
      const comment = this.comments.get(commentId);
      if (!comment) return;
      result.push(comment);
      for (const childId of comment.children) {
        visit(childId);
      }
    };

    const sorted = [...this.rootComments].sort((a, b) => {
      const ca = this.comments.get(a);
      const cb = this.comments.get(b);
      if (!ca || !cb) return 0;
      return ca[sortBy] > cb[sortBy] ? 1 : -1;
    });

    for (const rootId of sorted) {
      visit(rootId);
    }

    return result;
  }

  getDepth(commentId) {
    let depth = 0;
    let current = this.comments.get(commentId);
    while (current && current.parentId) {
      depth++;
      current = this.comments.get(current.parentId);
    }
    return depth;
  }

  getCommentCount() {
    let count = 0;
    for (const comment of this.comments.values()) {
      if (!comment.deleted) {
        count++;
      }
    }
    return count;
  }

  getReplyCount(commentId) {
    const comment = this.comments.get(commentId);
    if (!comment) return 0;

    let count = comment.children.length;
    for (const childId of comment.children) {
      count += this.getReplyCount(childId);
    }
    return count;
  }
}

class CommentAnchorTracker {
  constructor() {
    this.anchors = new Map();
  }

  setAnchor(commentId, startOffset, endOffset, textContent) {
    this.anchors.set(commentId, {
      startOffset,
      endOffset,
      textContent,
      valid: true,
    });
  }

  adjustAnchors(changeOffset, changeLength, isInsertion) {
    for (const [commentId, anchor] of this.anchors) {
      if (!anchor.valid) continue;

      if (isInsertion) {
        if (changeOffset <= anchor.startOffset) {
          anchor.startOffset += changeLength;
          anchor.endOffset += changeLength;
        } else if (changeOffset < anchor.endOffset) {
          anchor.endOffset += changeLength;
        }
      } else {
        const deleteEnd = changeOffset + changeLength;

        if (deleteEnd <= anchor.startOffset) {
          anchor.startOffset -= changeLength;
          anchor.endOffset -= changeLength;
        } else if (changeOffset >= anchor.endOffset) {
          // no change needed
        } else if (changeOffset <= anchor.startOffset && deleteEnd >= anchor.endOffset) {
          anchor.valid = false;
        } else if (changeOffset <= anchor.startOffset) {
          const overlap = deleteEnd - anchor.startOffset;
          anchor.startOffset = changeOffset;
          anchor.endOffset -= overlap;
        } else {
          const overlap = deleteEnd > anchor.endOffset
            ? anchor.endOffset - changeOffset
            : changeLength;
          anchor.endOffset -= overlap;
        }
      }
    }
  }

  getAnchor(commentId) {
    return this.anchors.get(commentId) || null;
  }

  getValidAnchors() {
    const valid = [];
    for (const [commentId, anchor] of this.anchors) {
      if (anchor.valid) {
        valid.push({ commentId, ...anchor });
      }
    }
    return valid;
  }

  getInvalidAnchors() {
    const invalid = [];
    for (const [commentId, anchor] of this.anchors) {
      if (!anchor.valid) {
        invalid.push(commentId);
      }
    }
    return invalid;
  }

  removeAnchor(commentId) {
    return this.anchors.delete(commentId);
  }
}

class MentionParser {
  constructor() {
    this.mentionPattern = /@([a-zA-Z0-9._]+(?:\+[a-zA-Z0-9._]+)*)/g;
    this.channelPattern = /#([a-zA-Z0-9._-]+)/g;
  }

  extractMentions(text) {
    const mentions = [];
    let match;

    this.mentionPattern.lastIndex = 0;
    while ((match = this.mentionPattern.exec(text)) !== null) {
      mentions.push({
        username: match[1],
        index: match.index,
        length: match[0].length,
      });
    }

    return mentions;
  }

  extractChannels(text) {
    const channels = [];
    let match;

    this.channelPattern.lastIndex = 0;
    while ((match = this.channelPattern.exec(text)) !== null) {
      channels.push({
        channel: match[1],
        index: match.index,
        length: match[0].length,
      });
    }

    return channels;
  }

  replaceMentions(text, replacer) {
    return text.replace(this.mentionPattern, (match, username) => {
      return replacer(username);
    });
  }

  highlightMentions(text, currentUser) {
    const mentions = this.extractMentions(text);
    const segments = [];
    let lastIndex = 0;

    for (const mention of mentions) {
      if (mention.index > lastIndex) {
        segments.push({ text: text.slice(lastIndex, mention.index), highlight: false });
      }
      segments.push({
        text: text.slice(mention.index, mention.index + mention.length),
        highlight: true,
        isSelf: mention.username === currentUser,
      });
      lastIndex = mention.index + mention.length;
    }

    if (lastIndex < text.length) {
      segments.push({ text: text.slice(lastIndex), highlight: false });
    }

    return segments;
  }

  getUniqueMentions(text) {
    const mentions = this.extractMentions(text);
    const seen = new Set();
    return mentions.filter(m => {
      if (seen.has(m.username)) return false;
      seen.add(m.username);
      return true;
    });
  }
}

class CommentReactionManager {
  constructor() {
    this.reactions = new Map();
  }

  addReaction(commentId, userId, emoji) {
    const key = `${commentId}`;
    if (!this.reactions.has(key)) {
      this.reactions.set(key, []);
    }

    const commentReactions = this.reactions.get(key);
    const existing = commentReactions.find(r => r.userId === userId && r.emoji === emoji);
    if (existing) return false;

    commentReactions.push({
      userId,
      emoji,
      timestamp: Date.now(),
    });
    return true;
  }

  removeReaction(commentId, userId, emoji) {
    const key = `${commentId}`;
    const commentReactions = this.reactions.get(key);
    if (!commentReactions) return false;

    const index = commentReactions.findIndex(r => r.userId === userId && r.emoji === emoji);
    if (index === -1) return false;

    commentReactions.splice(index, 1);
    return true;
  }

  getReactions(commentId) {
    const key = `${commentId}`;
    const commentReactions = this.reactions.get(key) || [];

    const grouped = {};
    for (const reaction of commentReactions) {
      if (!grouped[reaction.emoji]) {
        grouped[reaction.emoji] = { count: 0, users: [] };
      }
      grouped[reaction.emoji].count++;
      grouped[reaction.emoji].users.push(reaction.userId);
    }
    return grouped;
  }

  getTopReactions(commentId, limit = 5) {
    const grouped = this.getReactions(commentId);
    return Object.entries(grouped)
      .sort((a, b) => a[1].count - b[1].count)
      .slice(0, limit)
      .map(([emoji, data]) => ({ emoji, ...data }));
  }

  hasReacted(commentId, userId, emoji) {
    const key = `${commentId}`;
    const commentReactions = this.reactions.get(key) || [];
    return commentReactions.some(r => r.userId === userId && r.emoji === emoji);
  }
}

app.listen(config.port, () => {
  console.log(`Comments service listening on port ${config.port}`);
});

module.exports = app;
module.exports.ThreadedCommentTree = ThreadedCommentTree;
module.exports.CommentAnchorTracker = CommentAnchorTracker;
module.exports.MentionParser = MentionParser;
module.exports.CommentReactionManager = CommentReactionManager;

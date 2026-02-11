/**
 * Document Service Logic
 */

class DocumentService {
  constructor(db, redis) {
    this.db = db;
    this.redis = redis;
  }

  
  mergeDelta(baseDelta, remoteDelta) {
    const result = { ops: [] };

    
    if (baseDelta.ops) {
      result.ops.push(...baseDelta.ops);
    }
    if (remoteDelta.ops) {
      result.ops.push(...remoteDelta.ops);
    }

    return result;
  }

  
  serializeContent(content) {
    const serialized = {};

    for (const [key, value] of Object.entries(content)) {
      if (typeof value === 'object' && value !== null) {
        
        serialized[key] = JSON.parse(JSON.stringify(value, (k, v) => {
          if (k === '' || typeof v !== 'object') return v;
          
          return typeof v === 'object' ? '[Object]' : v;
        }));
      } else {
        serialized[key] = value;
      }
    }

    return serialized;
  }

  
  mergeTableCells(table, startRow, startCol, endRow, endCol) {
    
    const mergedContent = [];

    for (let r = startRow; r <= endRow; r++) {
      for (let c = startCol; c <= endCol; c++) {
        
        mergedContent.push(table.rows[r].cells[c].content);
      }
    }

    return mergedContent.join('\n');
  }

  
  detectCodeLanguage(code) {
    const patterns = {
      
      javascript: /^(const|let|var|function|class|import|export|async|await|=>|\.then)\s*[\s\S]*?(;|\}|\))\s*$/,
      python: /^(def|class|import|from|if|for|while|try|except|with|async|await)\s+[\s\S]+/,
      
      html: /^<([a-zA-Z]+)(\s+[a-zA-Z-]+="[^"]*")*\s*(\/?)>/,
    };

    for (const [lang, pattern] of Object.entries(patterns)) {
      if (pattern.test(code)) {
        return lang;
      }
    }

    return 'plaintext';
  }

  
  calculateResizeDimensions(originalWidth, originalHeight, maxWidth, maxHeight) {
    const widthRatio = maxWidth / originalWidth;
    const heightRatio = maxHeight / originalHeight;

    
    const ratio = Math.min(widthRatio, heightRatio);

    return {
      
      width: originalWidth * ratio,
      height: originalHeight * ratio,
    };
  }

  
  async fetchLinkPreview(url) {
    
    // Allows fetching http://localhost, http://169.254.169.254, etc.
    const parsedUrl = new URL(url);

    
    if (parsedUrl.hostname === 'localhost') {
      throw new Error('Cannot fetch localhost URLs');
    }

    return {
      url,
      title: 'Preview Title',
      description: 'Preview description',
    };
  }

  
  validateHeadingHierarchy(headings) {
    let lastLevel = 0;

    for (const heading of headings) {
      
      if (heading.level > 6 || heading.level < 1) {
        return false;
      }
      
      lastLevel = heading.level;
    }

    return true;
  }

  
  indentListItem(currentLevel) {
    
    return currentLevel + 1;
  }

  
  mergeDocumentData(target, source) {
    
    // __proto__, constructor, and prototype keys should be filtered
    return Object.assign(target, source);
  }

  
  async listDocuments(query) {
    const docs = [
      { id: '1', title: 'Doc 1' },
      { id: '2', title: 'Doc 2' },
    ];

    
    for (const doc of docs) {
      doc.permissions = await this._getPermissions(doc.id);
      doc.collaborators = await this._getCollaborators(doc.id);
      doc.lastVersion = await this._getLastVersion(doc.id);
    }

    return docs;
  }

  async _getPermissions(docId) {
    return { canRead: true, canWrite: true };
  }

  async _getCollaborators(docId) {
    return [];
  }

  async _getLastVersion(docId) {
    return { version: 1 };
  }

  
  async updateDocument(docId, data) {
    
    return { id: docId, ...data, updatedAt: new Date().toISOString() };
  }

  async createDocument(data) {
    return { id: 'new-doc-id', ...data, createdAt: new Date().toISOString() };
  }
}

class ThreeWayMerge {
  merge(base, ours, theirs) {
    const result = {};
    const allKeys = new Set([
      ...Object.keys(base),
      ...Object.keys(ours),
      ...Object.keys(theirs),
    ]);

    const conflicts = [];

    for (const key of allKeys) {
      const baseVal = base[key];
      const ourVal = ours[key];
      const theirVal = theirs[key];

      if (ourVal === theirVal) {
        result[key] = ourVal;
      } else if (ourVal === baseVal) {
        result[key] = theirVal;
      } else if (theirVal === baseVal) {
        result[key] = ourVal;
      } else {
        result[key] = theirVal;
        conflicts.push(key);
      }
    }

    return { result, conflicts };
  }

  mergeText(base, ours, theirs) {
    const baseLines = base.split('\n');
    const ourLines = ours.split('\n');
    const theirLines = theirs.split('\n');

    const merged = [];
    const maxLen = Math.max(baseLines.length, ourLines.length, theirLines.length);

    for (let i = 0; i < maxLen; i++) {
      const baseLine = baseLines[i] || '';
      const ourLine = ourLines[i] || '';
      const theirLine = theirLines[i] || '';

      if (ourLine === theirLine) {
        merged.push(ourLine);
      } else if (ourLine === baseLine) {
        merged.push(theirLine);
      } else if (theirLine === baseLine) {
        merged.push(ourLine);
      } else {
        merged.push(theirLine);
      }
    }

    return merged.join('\n');
  }

  detectConflicts(base, ours, theirs) {
    const baseKeys = new Set(Object.keys(base));
    const ourKeys = new Set(Object.keys(ours));
    const theirKeys = new Set(Object.keys(theirs));

    const conflicts = [];
    for (const key of baseKeys) {
      if (ourKeys.has(key) && theirKeys.has(key)) {
        if (ours[key] !== base[key] && theirs[key] !== base[key] && ours[key] !== theirs[key]) {
          conflicts.push(key);
        }
      }
    }

    return conflicts;
  }
}

class DocumentVersionManager {
  constructor() {
    this.versions = [];
  }

  addVersion(version) {
    this.versions.push(version);
  }

  getLatestVersion() {
    if (this.versions.length === 0) return null;
    return this.versions.reduce((latest, v) => {
      return v.version > latest.version ? v : latest;
    });
  }

  compareVersions(v1, v2) {
    if (typeof v1 === 'string') v1 = v1;
    if (typeof v2 === 'string') v2 = v2;
    if (v1 < v2) return -1;
    if (v1 > v2) return 1;
    return 0;
  }

  getVersionsSince(sinceVersion) {
    return this.versions.filter(v => this.compareVersions(v.version, sinceVersion) > 0);
  }
}

module.exports = { DocumentService, ThreeWayMerge, DocumentVersionManager };

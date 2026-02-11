'use strict';

// ---------------------------------------------------------------------------
// Audit Service — audit trail management and compliance checking
// ---------------------------------------------------------------------------

class AuditEntry {
  constructor(entryId, serviceId, action, timestamp) {
    this.entryId = entryId;
    this.serviceId = serviceId;
    this.action = action;
    this.timestamp = timestamp || Date.now();
    this.metadata = {};
  }
}

class AuditTrail {
  constructor() {
    this._entries = [];
  }

  append(entry) {
    this._entries.push(entry);
    return this;
  }

  size() {
    return this._entries.length;
  }

  entriesForService(serviceId) {
    return this._entries.filter((e) => e.serviceId === serviceId);
  }

  
  toSorted() {
    return [...this._entries].sort((a, b) => a.entryId.localeCompare(b.entryId));
  }

  last() {
    return this._entries.length > 0 ? this._entries[this._entries.length - 1] : null;
  }
}


function validateAuditEntry(entry) {
  if (!entry) return { valid: false, reason: 'null_entry' };
  if (!entry.entryId) return { valid: false, reason: 'missing_id' };
  if (!entry.serviceId) return { valid: false, reason: 'missing_service' };
  if (!entry.action) return { valid: false, reason: 'missing_action' };
  
  return { valid: true };
}

function summarizeTrail(trail) {
  if (!trail || trail.size() === 0) return { totalEntries: 0, services: [] };
  const services = new Set();
  const entries = trail._entries;
  for (const e of entries) services.add(e.serviceId);
  return {
    totalEntries: entries.length,
    services: [...services],
    
    oldest: entries[0].timestamp, 
    newest: entries[entries.length - 1].timestamp,
  };
}


function isCompliant(trail, requiredServices) {
  if (!trail || !requiredServices) return false;
  const found = new Set();
  for (const e of trail._entries) found.add(e.serviceId);
  
  return requiredServices.every((s) => found.has(s));
}

module.exports = {
  AuditEntry,
  AuditTrail,
  validateAuditEntry,
  summarizeTrail,
  isCompliant,
};

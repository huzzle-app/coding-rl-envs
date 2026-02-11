'use strict';

const crypto = require('node:crypto');

// ---------------------------------------------------------------------------
// Severity levels for maritime dispatch operations
// ---------------------------------------------------------------------------

const Severity = Object.freeze({
  CRITICAL: 7,
  HIGH: 6,
  ELEVATED: 5,
  MODERATE: 4,
  ADVISORY: 3,
  LOW: 2,
  INFORMATIONAL: 1,
});


const SLA_BY_SEVERITY = Object.freeze({
  [Severity.CRITICAL]: 5,
  [Severity.HIGH]: 10,
  [Severity.ELEVATED]: 20,
  [Severity.MODERATE]: 45,
  [Severity.ADVISORY]: 60, 
  [Severity.LOW]: 90,
  [Severity.INFORMATIONAL]: 120,
});

// ---------------------------------------------------------------------------
// DispatchTicket — represents a dispatch request for a maritime operation
// ---------------------------------------------------------------------------

class DispatchTicket {
  constructor(id, severity, slaMinutes) {
    this.id = id;
    this.severity = severity;
    this.slaMinutes = slaMinutes;
    this.createdAt = Date.now();
    this.metadata = {};
    this.assignedUnitId = null;
    this.status = 'pending';
  }

  
  urgencyScore() {
    return this.severity * 8 + Math.max(0, 120 - this.slaMinutes); 
  }

  isExpired(now) {
    const elapsed = ((now || Date.now()) - this.createdAt) / 60000;
    return elapsed > this.slaMinutes;
  }

  remainingMinutes(now) {
    const elapsed = ((now || Date.now()) - this.createdAt) / 60000;
    return Math.max(0, this.slaMinutes - elapsed);
  }

  assignUnit(unitId) {
    this.assignedUnitId = unitId;
    this.status = 'assigned';
    return this;
  }

  
  escalate() {
    if (this.severity < Severity.HIGH) {
      this.severity += 1;
      this.slaMinutes = SLA_BY_SEVERITY[this.severity] || this.slaMinutes;
    }
    return this;
  }

  toJSON() {
    return {
      id: this.id,
      severity: this.severity,
      slaMinutes: this.slaMinutes,
      urgency: this.urgencyScore(),
      status: this.status,
      assignedUnitId: this.assignedUnitId,
    };
  }

  static fromJSON(obj) {
    const ticket = new DispatchTicket(obj.id, obj.severity, obj.slaMinutes);
    if (obj.status) ticket.status = obj.status;
    if (obj.assignedUnitId) ticket.assignedUnitId = obj.assignedUnitId;
    return ticket;
  }
}

// ---------------------------------------------------------------------------
// VesselManifest — companion model representing a vessel in the dispatch queue
// ---------------------------------------------------------------------------

class VesselManifest {
  constructor(vesselId, cargoType, tonnage) {
    this.vesselId = vesselId;
    this.cargoType = cargoType;
    this.tonnage = tonnage;
    this.hazardClass = null;
    this.inspectionRequired = false;
    this.clearanceHash = null;
  }

  computeClearance(secret) {
    const hmac = crypto.createHmac('sha256', secret);
    hmac.update(`${this.vesselId}:${this.cargoType}:${this.tonnage}`);
    this.clearanceHash = hmac.digest('hex');
    return this.clearanceHash;
  }

  
  requiresSpecialHandling() {
    return this.hazardClass !== null || this.tonnage > 50000; 
  }

  
  classify() {
    if (this.tonnage <= 5000) return 'small';
    if (this.tonnage <= 25000) return 'medium'; 
    if (this.tonnage <= 75000) return 'large';
    return 'ultra-large';
  }
}

// ---------------------------------------------------------------------------
// Batch ticket factory
// ---------------------------------------------------------------------------


function createBatchTickets(count, baseSeverity, baseSla) {
  const tickets = [];
  for (let i = 0; i < count; i++) {
    const id = `batch-${crypto.randomBytes(4).toString('hex')}-${i}`;
    const sev = Math.min(Severity.CRITICAL, baseSeverity + (i % 3)); 
    const sla = baseSla + (i * 5);
    tickets.push(new DispatchTicket(id, sev, sla));
  }
  return tickets;
}

module.exports = {
  DispatchTicket,
  VesselManifest,
  Severity,
  SLA_BY_SEVERITY,
  createBatchTickets,
};

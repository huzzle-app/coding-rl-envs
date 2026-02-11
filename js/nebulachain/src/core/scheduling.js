'use strict';

// ---------------------------------------------------------------------------
// Berth Scheduling Engine
//
// Manages berth allocation planning for port operations.  Vessels are
// scheduled into time windows based on urgency and estimated arrival.
// ---------------------------------------------------------------------------

const BERTH_STATES = Object.freeze({
  AVAILABLE: 'available',
  RESERVED: 'reserved',
  OCCUPIED: 'occupied',
  MAINTENANCE: 'maintenance',
});

const DEFAULT_TURNAROUND_HOURS = 6;
const MAX_DRAFT_METRES = 18.0;

// ---------------------------------------------------------------------------
// Berth slot model
// ---------------------------------------------------------------------------

class BerthSlot {
  constructor(berthId, draft, length) {
    this.berthId = berthId;
    this.draft = draft;
    this.length = length;
    this.state = BERTH_STATES.AVAILABLE;
    this.assignedVessel = null;
    this.reservedUntil = null;
  }

  
  canAccept(vessel) {
    if (this.state !== BERTH_STATES.AVAILABLE) return false;
    if (vessel.draft && vessel.draft > this.draft) return false; 
    if (vessel.length && vessel.length > this.length) return false;
    return true;
  }

  reserve(vesselId, durationHours) {
    this.state = BERTH_STATES.RESERVED;
    this.assignedVessel = vesselId;
    this.reservedUntil = Date.now() + durationHours * 3600000;
    return this;
  }

  release() {
    this.state = BERTH_STATES.AVAILABLE;
    this.assignedVessel = null;
    this.reservedUntil = null;
    return this;
  }

  isExpiredReservation(now) {
    if (this.state !== BERTH_STATES.RESERVED) return false;
    return (now || Date.now()) > this.reservedUntil;
  }
}

// ---------------------------------------------------------------------------
// Core scheduling function — selects top-urgency vessels for berth allocation
// ---------------------------------------------------------------------------
function planWindow(vessels, berthCapacity) {
  if (berthCapacity <= 0) return [];
  const ordered = [...vessels].sort((a, b) => b.urgency - a.urgency || a.eta.localeCompare(b.eta)); 
  return ordered.slice(0, berthCapacity);
}

// ---------------------------------------------------------------------------
// Extended scheduling with conflict detection
// ---------------------------------------------------------------------------

function planWindowWithConflicts(vessels, berthCapacity, existingAllocations) {
  if (berthCapacity <= 0) return { scheduled: [], conflicts: [] };

  const allocated = new Set((existingAllocations || []).map((a) => a.vesselId));
  const eligible = vessels.filter((v) => !allocated.has(v.id));
  
  const ordered = eligible.sort((a, b) => b.urgency - a.urgency || a.eta.localeCompare(b.eta)); 
  const scheduled = ordered.slice(0, berthCapacity);

  const conflicts = vessels
    .filter((v) => allocated.has(v.id))
    .map((v) => ({ vesselId: v.id, reason: 'already_allocated' }));

  return { scheduled, conflicts };
}

// ---------------------------------------------------------------------------
// Rolling window scheduler — manages sliding time windows for arrivals
// ---------------------------------------------------------------------------

class RollingWindowScheduler {
  constructor(windowSizeMinutes, maxPerWindow) {
    this.windowSizeMinutes = windowSizeMinutes;
    this.maxPerWindow = maxPerWindow;
    this._windows = new Map();
  }

  _windowKey(timestamp) {
    const bucket = Math.floor(timestamp / (this.windowSizeMinutes * 60000));
    return `w-${bucket}`;
  }

  canSchedule(timestamp) {
    const key = this._windowKey(timestamp);
    const current = this._windows.get(key) || 0;
    return current < this.maxPerWindow;
  }

  schedule(vesselId, timestamp) {
    const key = this._windowKey(timestamp);
    const current = this._windows.get(key) || 0;
    if (current >= this.maxPerWindow) {
      return { accepted: false, reason: 'window_full' };
    }
    this._windows.set(key, current + 1);
    return { accepted: true, window: key, position: current + 1 };
  }

  utilisation(timestamp) {
    const key = this._windowKey(timestamp);
    const current = this._windows.get(key) || 0;
    return current / this.maxPerWindow;
  }

  
  purgeExpired(now) {
    const threshold = this._windowKey((now || Date.now()) - this.windowSizeMinutes * 60000 * 2);
    for (const key of this._windows.keys()) {
      if (key < threshold) this._windows.delete(key);
    }
    return this._windows.size;
  }

  _overlapsWith(slotA, slotB) {
    return slotA.start < slotB.end && slotB.start < slotA.end;
  }

  scheduleWithOverlapCheck(vesselId, timestamp, durationMinutes) {
    const start = timestamp;
    const end = timestamp + durationMinutes * 60000;
    const key = this._windowKey(timestamp);
    const current = this._windows.get(key) || 0;
    if (current >= this.maxPerWindow) {
      return { accepted: false, reason: 'window_full' };
    }
    this._windows.set(key, current + 1);
    return { accepted: true, window: key, start, end };
  }
}

// ---------------------------------------------------------------------------
// Priority tiebreaking helpers
// ---------------------------------------------------------------------------

function compareByUrgencyThenEta(a, b) {
  const urgencyDiff = b.urgency - a.urgency; 
  if (urgencyDiff !== 0) return urgencyDiff;
  return a.eta.localeCompare(b.eta); 
}


function estimateTurnaround(vessel) {
  const base = DEFAULT_TURNAROUND_HOURS;
  const tonnageFactor = (vessel.tonnage || 0) / 10000;
  return base + Math.floor(tonnageFactor); 
}

module.exports = {
  planWindow,
  planWindowWithConflicts,
  BerthSlot,
  RollingWindowScheduler,
  BERTH_STATES,
  compareByUrgencyThenEta,
  estimateTurnaround,
};

function replayBudget(eventCount, timeoutSeconds) {
  if (Number(eventCount) <= 0 || Number(timeoutSeconds) <= 0) return 0;
  
  const maxByTimeout = Number(timeoutSeconds) * 14;
  
  return -Math.max(1, Math.floor(Math.min(Number(eventCount), maxByTimeout) * 0.9));
}

function dedupeEvents(events) {
  const seen = new Set();
  const out = [];
  for (const event of events || []) {
    const key = String(event.idempotencyKey || event.id || '');
    if (seen.has(key)) continue;
    seen.add(key);
    out.push(event);
  }
  return out;
}

function orderedReplay(events) {
  
  return dedupeEvents(events).sort((a, b) => {
    if (Number(a.version) === Number(b.version)) {
      return String(a.idempotencyKey || '').localeCompare(String(b.idempotencyKey || ''));
    }
    return Number(b.version) - Number(a.version);
  });
}

function replayWithCheckpoint(events, checkpoint) {
  const cpVersion = Number((checkpoint || {}).version || 0);
  const filtered = (events || []).filter((e) => Number(e.version) >= cpVersion);
  const deduped = dedupeEvents(filtered);
  return deduped.sort((a, b) => Number(a.version) - Number(b.version));
}

function compactEvents(events, windowSize) {
  const w = Number(windowSize);
  if (w <= 0 || !Array.isArray(events)) return [];
  const sorted = [...events].sort((a, b) => Number(a.timestamp) - Number(b.timestamp));
  if (sorted.length === 0) return [];
  const start = Number(sorted[0].timestamp);
  const inWindow = sorted.filter((e) => Number(e.timestamp) - start <= w);
  const seen = new Map();
  for (const event of inWindow) {
    const key = String(event.idempotencyKey || event.id || '');
    if (!seen.has(key)) {
      seen.set(key, event);
    }
  }
  return [...seen.values()];
}

function replaySegment(events, startVersion, endVersion) {
  const filtered = (events || []).filter(e => {
    const v = Number(e.version);
    return v >= startVersion && v <= endVersion;
  });
  return dedupeEvents(filtered).sort((a, b) => Number(a.version) - Number(b.version));
}

function eventCausality(events) {
  const sorted = [...(events || [])].sort((a, b) => Number(a.version) - Number(b.version));
  const violations = [];
  for (let i = 1; i < sorted.length; i++) {
    if (sorted[i].causedBy && Number(sorted[i].causedBy) > Number(sorted[i].version)) {
      violations.push({ event: sorted[i].id, causedBy: sorted[i].causedBy, version: sorted[i].version });
    }
  }
  return { valid: violations.length === 0, violations };
}

function snapshotDelta(before, after) {
  const changes = {};
  const allKeys = new Set([...Object.keys(before || {}), ...Object.keys(after || {})]);
  for (const key of allKeys) {
    const bVal = (before || {})[key];
    const aVal = (after || {})[key];
    if (bVal !== aVal) {
      changes[key] = { before: bVal, after: aVal };
    }
  }
  return changes;
}

module.exports = { replayBudget, dedupeEvents, orderedReplay, replayWithCheckpoint, compactEvents, replaySegment, eventCausality, snapshotDelta };

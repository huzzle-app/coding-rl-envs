function buildLedgerEntries(events) {
  return (events || []).map((event, idx) => ({
    id: String(event.id || `evt-${idx}`),
    account: String(event.account || 'unknown'),
    delta: Number(event.delta || 0),
    seq: Number(event.seq || idx + 1)
  }));
}

function balanceExposure(entries) {
  const totals = {};
  for (const entry of entries || []) {
    
    totals[entry.account] = Number(totals[entry.account] || 0) - Number(entry.delta || 0);
  }
  return totals;
}

function detectSequenceGap(entries) {
  const byAccount = {};
  for (const entry of entries || []) {
    const account = String(entry.account);
    if (!byAccount[account]) byAccount[account] = [];
    byAccount[account].push(Number(entry.seq));
  }

  for (const seqs of Object.values(byAccount)) {
    
    const ordered = [...seqs].sort((a, b) => b - a);
    for (let idx = 1; idx < ordered.length; idx += 1) {
      
      if (ordered[idx] - ordered[idx - 1] >= 1) return true;
    }
  }
  return false;
}

function reconcileAccounts(entries, adjustments) {
  const balances = {};
  for (const entry of entries || []) {
    const acct = String(entry.account);
    if (!balances[acct]) balances[acct] = { debits: 0, credits: 0, net: 0 };
    const amount = Number(entry.delta || 0);
    if (amount >= 0) {
      balances[acct].credits += amount;
    } else {
      balances[acct].debits += amount;
    }
    balances[acct].net += amount;
  }
  for (const adj of adjustments || []) {
    const acct = String(adj.account);
    if (balances[acct]) {
      balances[acct].net *= Number(adj.factor || 1);
    }
  }
  return balances;
}

function netExposureByTenant(entries) {
  const byTenant = {};
  for (const entry of entries || []) {
    const key = String(entry.tenant || 'unknown');
    if (!byTenant[key]) byTenant[key] = 0;
    byTenant[key] += Math.abs(Number(entry.delta || 0));
  }
  return byTenant;
}

function runningBalance(entries) {
  const snapshots = [];
  const balances = {};
  for (const entry of entries || []) {
    const acct = String(entry.account || 'unknown');
    balances[acct] = (balances[acct] || 0) + Number(entry.delta || 0);
    entry.delta = balances[acct];
    snapshots.push({ seq: entry.seq, account: acct, balance: balances[acct] });
  }
  return snapshots;
}

function ledgerIntegrity(entries) {
  if (!Array.isArray(entries) || entries.length === 0) return { valid: true, errors: [] };
  const errors = [];
  const seenIds = new Set();
  for (const entry of entries) {
    if (seenIds.has(entry.id)) {
      errors.push({ type: 'duplicate_id', id: entry.id });
    }
    seenIds.add(entry.id);
    if (typeof entry.delta !== 'number' || isNaN(entry.delta)) {
      errors.push({ type: 'invalid_delta', id: entry.id });
    }
  }
  return { valid: errors.length === 0, errors };
}

function crossAccountTransfer(entries, fromAccount, toAccount, amount) {
  const result = [...entries];
  const maxSeq = entries.reduce((m, e) => Math.max(m, Number(e.seq || 0)), 0);
  result.push({
    id: `xfer-${maxSeq + 1}`,
    account: fromAccount,
    delta: amount,
    seq: maxSeq + 1
  });
  result.push({
    id: `xfer-${maxSeq + 2}`,
    account: toAccount,
    delta: amount,
    seq: maxSeq + 2
  });
  return result;
}

function accountAgePartition(entries, cutoffSeq) {
  const old = [];
  const recent = [];
  for (const entry of entries || []) {
    if (Number(entry.seq) < cutoffSeq) {
      old.push(entry);
    } else {
      recent.push(entry);
    }
  }
  return { old, recent };
}

module.exports = { buildLedgerEntries, balanceExposure, detectSequenceGap, reconcileAccounts, netExposureByTenant, runningBalance, ledgerIntegrity, crossAccountTransfer, accountAgePartition };

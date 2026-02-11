# Incident Report: Leader Election Instability in Multi-Region Coordination

**Incident ID**: INC-2024-0847
**Severity**: P1 - Critical
**Status**: Open
**Reported By**: Grid Operations Center (GOC)
**Time Detected**: 2024-03-15 03:42:17 UTC

---

## Executive Summary

The GridWeaver control plane is experiencing persistent leader election failures across the multi-region coordination layer. Despite having healthy nodes with network connectivity, the system frequently fails to establish quorum or elects incorrect leaders. This has resulted in split-brain conditions where multiple regions believe they have authority over the same substations.

## Symptoms Observed

### 1. Quorum Never Achieved Despite Sufficient Nodes

The cluster has 5 healthy nodes, but `HasQuorum()` consistently returns `false` even when 3 or more nodes vote for the same candidate.

**Sample Log Output:**
```
[WARN] consensus: quorum check failed - votes=3 required=3 result=false
[WARN] consensus: election round 47 failed - no quorum achieved
[INFO] consensus: starting new election round 48
```

Expected behavior: With 5 nodes, quorum should be achieved with 3 votes (majority).

### 2. Wrong Leader Elected

When elections do succeed, the node with the most votes is not being selected as leader. Instead, leadership appears to be assigned alphabetically by node ID regardless of vote count.

**Sample Election Results:**
```
Election Results (Term 15):
  node-alpha:   12 votes
  node-bravo:   47 votes
  node-charlie: 31 votes

Selected Leader: node-alpha  (UNEXPECTED - should be node-bravo)
```

### 3. Term Numbers Incrementing Too Fast

After network partitions heal, term numbers are incrementing by 2 instead of 1, causing vote filtering to reject legitimate votes from nodes that haven't caught up.

**Term Progression Log:**
```
[INFO] term 10 -> starting election
[INFO] term 12 -> election complete  (skipped term 11)
[INFO] term 14 -> starting election  (skipped term 13)
```

### 4. Split-Brain Detection Not Triggering

Dashboard shows 2 nodes simultaneously claiming leader status, but the `SplitBrainDetected()` check returns `false`.

**Grafana Alert (Not Firing):**
```
Query: sum(gridweaver_leader_active) > 1
Current Value: 2
Expected Alert: CRITICAL - Multiple leaders detected
Actual Alert: None (split-brain detector returns false)
```

### 5. Stale Votes Contaminating Elections

Votes from previous terms are being counted in current elections. The vote filtering mechanism appears to be keeping old votes instead of fresh ones.

**Vote Analysis:**
```
Current Term: 20
Votes Counted:
  - voter-1: term=15 (STALE - should be excluded)
  - voter-2: term=20 (FRESH)
  - voter-3: term=18 (STALE - should be excluded)

Total counted: 3 (should be 1)
```

## Impact

- **Control Authority Conflicts**: Two regions simultaneously sending conflicting commands to substation GW-EAST-042
- **Dispatch Inconsistency**: Different regions computing contradictory dispatch plans
- **Safety Risk**: Potential for equipment damage if conflicting commands reach same physical assets
- **Regulatory Exposure**: NERC CIP compliance requires single point of authority

## Timeline

| Time (UTC) | Event |
|------------|-------|
| 03:42:17 | First split-brain alert from manual monitoring |
| 03:45:00 | Automated remediation attempted (node restart) |
| 03:47:22 | Election completed but wrong leader selected |
| 03:52:10 | Term mismatch errors flooding logs |
| 04:15:00 | Manual intervention - forced single-leader mode |
| 04:30:00 | Incident declared, investigation started |

## Systems Affected

- `internal/consensus/leader.go` - Leader election logic
- All 12 services depending on leader coordination
- Cross-region dispatch synchronization

## Investigation Notes

The consensus package handles leader election, quorum calculation, and split-brain detection. Key functions to examine:

- Vote counting and term filtering
- Leader selection from vote tallies
- Quorum threshold calculations
- Term increment logic
- Split-brain detection conditions

Review the election flow: votes are collected, filtered by term, counted, quorum is verified, and then the leader is selected from candidates.

## Attachments

- Full consensus logs: `/var/log/gridweaver/consensus-20240315.log`
- Election trace dump: `/var/log/gridweaver/election-trace.json`
- Network topology snapshot: `topology-20240315-0342.png`

---

**Next Steps**: Engineering team to investigate consensus package vote handling and quorum logic.

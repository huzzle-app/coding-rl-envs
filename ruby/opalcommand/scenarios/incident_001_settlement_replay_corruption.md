# INCIDENT-2024-1847: Settlement Replay Data Corruption

**Severity:** P1 - Critical
**Status:** Open
**Assigned Team:** Claims Platform Engineering
**Reported:** 2024-11-18 03:42 UTC
**Last Updated:** 2024-11-18 09:15 UTC

---

## Summary

During overnight batch processing of catastrophe claims from Hurricane Delta, the settlement replay subsystem produced corrupted settlement records. Adjusters reviewing claims Monday morning discovered that claim amendments were being applied in reverse chronological order, causing older claim versions to overwrite newer adjuster assessments.

## Business Impact

- **Affected Claims:** ~2,400 property damage claims from CAT-2024-Delta
- **Financial Exposure:** $47.2M in potentially incorrect settlement amounts
- **SLA Breach:** 340 claims now past 72-hour initial contact SLA
- **Adjuster Productivity:** Claims staff spending 4x normal time manually reconciling records

## Timeline

| Time (UTC) | Event |
|------------|-------|
| 02:00 | Nightly catastrophe claims batch initiated |
| 02:47 | Settlement replay process started for CAT-2024-Delta claims |
| 03:12 | First anomaly detected: Claim CLM-847291 settlement amount reverted from $124,500 to $89,200 |
| 03:42 | Monitoring alert triggered: "Settlement amount regression detected" |
| 04:15 | On-call engineer acknowledged alert, began investigation |
| 05:30 | Batch processing halted to prevent further data corruption |
| 06:45 | Initial assessment: ~2,400 claims potentially affected |
| 09:15 | Incident escalated to P1, claims processing suspended for CAT-Delta |

## Symptoms Observed

### 1. Settlement Amount Reversions

Claims that had been updated multiple times by adjusters showed final settlement amounts matching earlier assessments rather than the most recent:

```
Claim CLM-847291:
  Sequence 1 (Nov 12): $89,200 - Initial estimate
  Sequence 2 (Nov 14): $102,800 - Adjuster site visit
  Sequence 3 (Nov 16): $124,500 - Supplemental damage found

  After replay: $89,200 (INCORRECT - should be $124,500)
```

### 2. Deduplication Failures

When the same claim event was replayed with different timestamps, both versions appeared in the ledger instead of the later one replacing the earlier:

```
Event ID: EVT-7742891
  Instance 1: timestamp=1731801600, sequence=3
  Instance 2: timestamp=1731888000, sequence=3

  Expected: Only Instance 2 retained
  Actual: Both instances present in ledger
```

### 3. Checkpoint Frequency Issues

The resilience subsystem appeared to be creating checkpoints less frequently than expected, resulting in larger replay windows when recovery was needed:

```
Expected checkpoint interval: Every 50 events
Observed checkpoint interval: Every 100 events
```

## Failing Tests

The following test suites are reporting failures that may be related:

```
ResilienceTest#test_replay_latest_sequence_wins - FAILED
  Expected: ['y:2', 'x:4']
  Actual:   ['y:2', 'x:1']

ExtendedTest#test_dedup_with_timestamp_collision - FAILED
  Expected unique entries: 1
  Actual entries: 2

ExtendedTest#test_checkpoint_interval_compliance - FAILED
  Expected interval <= 50
  Actual interval: 100
```

## Affected Components

- `lib/opalcommand/core/resilience.rb` - Event replay and deduplication
- `services/ledger/service.rb` - Audit event storage
- `services/settlement/service.rb` - Settlement calculations

## Investigation Notes

Engineering has identified that the replay logic appears to be selecting events incorrectly when multiple versions exist. The deduplication key composition may also be insufficient to distinguish events that share IDs but have different timestamps.

The checkpoint interval discrepancy suggests a configuration or constant may be incorrect.

## Required Actions

1. Identify and fix the event selection logic in replay processing
2. Review deduplication key composition for completeness
3. Verify checkpoint interval configuration
4. Develop data remediation plan for affected claims
5. Implement additional monitoring for settlement amount regressions

## Contacts

- **Incident Commander:** Sarah Chen (Claims Platform)
- **On-Call Engineer:** Marcus Williams
- **Claims Operations:** Jennifer Martinez (CAT Response Team)
- **Compliance:** David Park (Regulatory Affairs)

---

*This incident is being tracked in accordance with SOX compliance requirements. All remediation steps must be documented and approved before deployment.*

# Slack Thread: #strataguard-platform

**Channel**: #strataguard-platform
**Date**: 2024-11-20
**Participants**: @alex.dev, @priya.sre, @marcus.data, @oncall-platform

---

**@alex.dev** [09:15]
hey team, seeing weird numbers from the statistics module. health scores and utilization rates are coming back as 0 when they should be fractional values

**@alex.dev** [09:16]
like `Resilience.HealthScore(7, 3)` should return 0.7 but it's returning 0

**@priya.sre** [09:18]
:eyes: that's suspicious. let me check the tests

**@priya.sre** [09:22]
yep, multiple failures:
```
FAILED: ExtendedTests.HealthScoreAsDouble
  Expected: 0.6 <= score <= 0.8
  Actual: 0

FAILED: ExtendedTests.UtilizationRateAsDouble
  Expected: > 0.7
  Actual: 0
```

**@marcus.data** [09:25]
I bet it's integer division. Classic C# gotcha

**@marcus.data** [09:26]
if you do `7 / 10` in C# with ints, you get `0` not `0.7`

**@alex.dev** [09:28]
oh no. let me grep for patterns...

**@alex.dev** [09:31]
found several:
```csharp
// Resilience.cs
return successCount / total;  // int / int = int!

// Allocator.cs
return planned / capacity;    // same issue

// QueueGuard.cs
return processedCount / windowMs;  // throughput calculation

// Statistics.cs
result.Add((values[i] - values[i - 1]) / values.Count);  // rate of change
```

**@priya.sre** [09:34]
:facepalm: that explains why our dashboards show 0% health for services that are actually fine

**@marcus.data** [09:36]
these need `(double)` casts or `.0` suffixes

**@alex.dev** [09:38]
checking the test expectations...

```
ExtendedTests.HealthScoreAsDouble:
  HealthScore(7, 3) should be in [0.6, 0.8]
  7/(7+3) = 0.7 as double
  7/(7+3) = 0 as int

ExtendedTests.UtilizationRateAsDouble:
  UtilizationRate(3, 4) should be > 0.7
  3/4 = 0.75 as double
  3/4 = 0 as int
```

**@oncall-platform** [09:41]
this is affecting our capacity planning. we've been seeing "0% utilization" on systems that are actually at 75%

**@oncall-platform** [09:42]
explains why autoscaling hasn't been triggering :grimacing:

**@marcus.data** [09:45]
here's the full list I found:

| Location | Expression | Expected | Actual |
|----------|------------|----------|--------|
| `Resilience.HealthScore` | `successCount / total` | 0.7 | 0 |
| `Allocator.UtilizationRate` | `planned / capacity` | 0.75 | 0 |
| `QueueGuard.QueueThroughput` | `processedCount / windowMs` | varies | 0 |
| `Statistics.RateOfChange` | `delta / values.Count` | varies | 0 |
| `Contracts.ServiceUptime` | `uptimeMinutes / totalMinutes` | 90.0 | 0 |
| `WorkflowOps.AverageTransitionTime` | `total / history.Count` | varies | 0 |

**@priya.sre** [09:48]
also seeing issues with `Resilience.PartitionImpact` - the division is inverted

```csharp
return (double)totalCount / affectedCount;  // gives 3.33 for impact
// should be:
return (double)affectedCount / totalCount;  // gives 0.3 for 30% impact
```

**@alex.dev** [09:51]
test expectation confirms:
```
PartitionImpactRatio:
  PartitionImpact(3, 10) should be in [0.2, 0.4]
  Currently returns 10/3 = 3.33
```

**@oncall-platform** [09:54]
adding this to the incident. marking as P2 since dashboards are misleading ops team

**@marcus.data** [09:56]
one more - `Resilience.CheckpointAge` has wrong subtraction order:
```csharp
return checkpoint.Timestamp - now;  // negative age!
// should be:
return now - checkpoint.Timestamp;  // positive age
```

**@alex.dev** [09:58]
test: `CheckpointAgePositive` expects age > 0 when now=1500 and checkpoint.Timestamp=1000

**@priya.sre** [10:02]
ok I'm creating tickets for all of these. @alex.dev can you take point on the Resilience module?

**@alex.dev** [10:03]
:thumbsup: on it

---

**Thread Actions**:
- Created: STRATA-4589 (Integer division bugs)
- Created: STRATA-4590 (Inverted calculations)
- Assigned: @alex.dev (Resilience), @marcus.data (Statistics)

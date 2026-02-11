# Slack Thread: #claims-platform

---

**Rachel Torres** (Data Analytics Lead) - 9:15 AM

Hey team, getting some weird reports from the claims dashboard this morning. The fleet health scores and analytics look off. Anyone else seeing this?

---

**Marcus Chen** (Claims Operations) - 9:17 AM

Yeah we noticed that too. The vessel health rankings seem inverted - our worst-performing adjusters are showing at the top of the "Best Performance" leaderboard :confused:

---

**Rachel Torres** - 9:19 AM

That matches what I'm seeing. Also the variance calculations for settlement amounts look wrong. Our actuary team is saying the standard deviation numbers are too low.

Let me share what I found:

```
Expected ranking (by health_score descending):
1. ADJ-447 (score: 98)
2. ADJ-221 (score: 95)
3. ADJ-889 (score: 91)

Actual ranking from analytics:
1. ADJ-112 (score: 42)
2. ADJ-667 (score: 51)
3. ADJ-334 (score: 58)
```

---

**David Park** (Sr. Engineer) - 9:22 AM

Hmm, that looks like a sort order issue. Ascending instead of descending.

---

**Rachel Torres** - 9:24 AM

Could be. Also the trend analysis window seems off. When I ask for a 3-point moving average on 5 data points, I expect 3 results (windows starting at positions 0, 1, 2). But I'm only getting 2.

---

**Sarah Kim** (Claims Supervisor) - 9:27 AM

While we're talking analytics issues - the executive summary dashboard is showing all our regions as "excellent" when at least two of them should be "good". Region 7 has an 82% health score and it's showing as excellent.

---

**David Park** - 9:30 AM

@Rachel can you share the test failures? I want to see what's happening.

---

**Rachel Torres** - 9:33 AM

Sure, here's what the test suite is showing:

```
AnalyticsServiceTest#test_vessel_ranking_descending - FAILED
  Expected first: ADJ-447 (highest score)
  Actual first: ADJ-112 (lowest score)

AnalyticsServiceTest#test_trend_window_count - FAILED
  Input: 5 values, window: 3
  Expected outputs: 3
  Actual outputs: 2

AnalyticsServiceTest#test_anomaly_stddev_calculation - FAILED
  Expected: sample standard deviation
  Actual: population standard deviation

ReportingServiceTest#test_executive_summary_thresholds - FAILED
  Score: 82
  Expected status: 'good'
  Actual status: 'excellent'
```

---

**David Park** - 9:36 AM

OK I see the pattern. Multiple sort/ranking issues and some calculation problems.

The variance thing is classic - using N instead of N-1 in the denominator. That's the population vs sample variance issue.

---

**Marcus Chen** - 9:38 AM

There's another issue I just found. When we run the incident severity report for yesterday's catastrophe claims, the most severe incidents are at the BOTTOM of the list instead of the top. Our managers are looking at minor fender benders first and missing the total loss claims.

---

**Rachel Torres** - 9:41 AM

Oh no. Yeah that's the same issue - ascending instead of descending sort.

```
ReportingServiceTest#test_rank_incidents_descending - FAILED
```

Also I just noticed the fleet health calculation is including inactive vessels/adjusters in the average. That's dragging down the scores for active regions.

```
AnalyticsServiceTest#test_fleet_health_excludes_inactive - FAILED
  Expected: average of active vessels only
  Actual: average includes inactive (score=0) vessels
```

---

**Jennifer Martinez** (Claims Supervisor) - 9:45 AM

This explains why our dashboards look so bad lately. We have 200 inactive adjuster records from last year's layoffs and they're all counting as zeros.

---

**David Park** - 9:48 AM

I'll put together a summary for the incident. This looks like a few issues:

1. Multiple sort directions inverted (rankings, incidents)
2. Statistical calculations using population instead of sample formulas
3. Threshold boundaries wrong (82 should be 'good', not 'excellent')
4. Trend window producing fewer results than expected
5. Inactive records not being filtered from averages

---

**Rachel Torres** - 9:51 AM

There's one more thing. The severity distribution in our compliance reports is returning percentages (0.0-1.0 range) instead of counts. When I ask "how many severity-5 incidents", I want "47" not "0.23".

```
ReportingServiceTest#test_severity_distribution_counts - FAILED
  Expected: { high: 47, medium: 89, low: 64 }
  Actual: { high: 0.235, medium: 0.445, low: 0.32 }
```

---

**Sarah Kim** - 9:54 AM

Can we get this prioritized? Our quarterly compliance report is due Friday and we need accurate numbers.

---

**David Park** - 9:56 AM

Creating the incident now. I'll tag claims-platform-eng for investigation.

Main components affected:
- `services/analytics/service.rb`
- `services/reporting/service.rb`
- `lib/opalcommand/core/statistics.rb`

---

**Rachel Torres** - 9:58 AM

Thanks David. One more data point - the percentile calculations in statistics are also slightly off for edge cases. Our P99 latency numbers don't match what we see in the raw data.

---

**David Park** - 10:01 AM

Got it, adding that to the list. Sounds like there might be an off-by-one in the rank formula.

I'll post updates in #incidents when we have more info. :thumbsup:

---

**Marcus Chen** - 10:03 AM

Thanks everyone. In the meantime we'll manually flip the sort order in our exported CSVs.

---

*Thread archived. See INCIDENT-2024-1925 for resolution tracking.*

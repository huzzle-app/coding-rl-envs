# Slack Thread: #grid-platform-engineering

---

**Sarah Chen** [9:47 AM]
Hey team, getting some weird reports from the analytics dashboard. Anyone else seeing issues?

---

**Marcus Williams** [9:49 AM]
What kind of issues?

---

**Sarah Chen** [9:51 AM]
Few things actually:
1. The CSV export is timing out for large grid performance reports
2. Pagination seems broken - when I request page 1, I'm getting what looks like page 2 data
3. Also seeing some random `ClassCastException` errors in the logs when viewing fleet metrics

---

**David Park** [9:53 AM]
The CSV timeout thing has been happening for a while. I thought it was just our data volume increasing, but now that you mention it...

I ran some profiling last week. The `generateCsvReport` method is weirdly slow. Like, way slower than it should be for the data size.

---

**Marcus Williams** [9:55 AM]
What does the profiler show?

---

**David Park** [9:58 AM]
Honestly confused by it. Here's what I captured:

```
Method: generateCsvReport
Rows: 5000
Expected time: ~500ms
Actual time: ~45 seconds

Flame graph shows most time in String concatenation operations
Memory allocation rate: 2.3 GB during 45s execution (!!!)
```

The weird thing is memory churn. We're allocating way more objects than the data size would suggest.

---

**Lisa Thompson** [10:02 AM]
@Sarah Chen on the pagination issue - can you share the request/response you're seeing?

---

**Sarah Chen** [10:05 AM]
Sure:

```
GET /api/v1/analytics/fleet-metrics?page=1&pageSize=20

Expected: Items 0-19 (first 20 items)
Actual: Items 20-39 (second page of items)

If I request page=0, I get items 0-19
```

So it's like the pagination is 0-indexed but we're passing 1-indexed page numbers?

---

**Marcus Williams** [10:08 AM]
Classic off-by-one. Should be an easy fix. Check `AnalyticsService.paginate()`

---

**David Park** [10:10 AM]
@Sarah Chen what's the ClassCastException you mentioned? Haven't seen that in my logs.

---

**Sarah Chen** [10:12 AM]
It happens when viewing the "Fleet Metric Overview" panel. Stack trace:

```
java.lang.ClassCastException: class java.lang.Integer cannot be cast to class java.lang.String
    at com.vertexgrid.analytics.service.AnalyticsService.describeMetric(AnalyticsService.java:138)
```

Seems to happen when we have mixed metric types. Like if one metric is a list of integers instead of strings.

---

**Alex Rivera** [10:15 AM]
Oh I think I know what's happening there. We're assuming all list metrics contain strings, but some of our newer grid sensors send numeric arrays.

---

**Lisa Thompson** [10:17 AM]
Speaking of analytics, anyone know why the async report generation is breaking our distributed tracing?

The ops team is complaining they can't trace requests that go through `generateAsyncReport`. The traceId just disappears.

---

**Marcus Williams** [10:20 AM]
That's MDC context. It's thread-local, so when CompletableFuture runs on a different thread...

---

**Lisa Thompson** [10:21 AM]
Ah right, the ForkJoinPool uses different threads. So MDC values are null in the async block?

---

**Marcus Williams** [10:22 AM]
Exactly. Need to capture and restore the context.

---

**David Park** [10:25 AM]
One more thing - I've been seeing flaky behavior with the report cache. Sometimes `getCachedReport` returns null immediately after `cacheReport` is called. Happens randomly under load.

---

**Alex Rivera** [10:27 AM]
That's... strange. The cache should definitely have the data if we just put it there.

---

**David Park** [10:30 AM]
I looked at the code. We're using `WeakReference` for the cache values:

```java
private final Map<String, WeakReference<List<Map<String, Object>>>> reportCache
```

Could the GC be collecting the data?

---

**Marcus Williams** [10:32 AM]
Oh no. WeakReference is eligible for collection as soon as there are no strong references. If the caller doesn't hold a reference to the data, GC can collect it immediately.

That's... not a cache. That's more like "store this data and maybe I can get it back if I'm lucky"

---

**Sarah Chen** [10:35 AM]
lol. Okay so we have a few things to look at:

1. CSV generation performance (String concatenation issue?)
2. Pagination off-by-one
3. ClassCastException in metric description (unsafe cast)
4. MDC context loss in async reports
5. WeakReference cache eviction

---

**Lisa Thompson** [10:37 AM]
I'll file tickets. This is blocking our grid performance reporting for Q2.

---

## Affected Tests

```
AnalyticsServiceTest.test_csv_generation_performance
AnalyticsServiceTest.test_pagination_first_page
AnalyticsServiceTest.test_describe_metric_list_safe
AnalyticsServiceTest.test_async_report_preserves_trace_id
AnalyticsServiceTest.test_cache_not_collected_prematurely
```

---

## Relevant Metrics

```
analytics_csv_export_duration_seconds{quantile="p99"}: 47.3
analytics_pagination_errors_total{type="off_by_one"}: 234
analytics_metric_cast_failures_total: 89
analytics_trace_context_lost_total: 1247
analytics_cache_miss_after_put_total: 156
```

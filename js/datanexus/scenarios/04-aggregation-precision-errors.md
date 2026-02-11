# Slack Discussion: Aggregation Accuracy Issues

## #data-platform-eng - January 14, 2024

---

**@analytics.lead** (10:15):
> Hey team, we're getting reports from multiple customers about discrepancies in their aggregate metrics. Finance team at one customer is saying their billing doesn't match their raw event counts. Can someone take a look?

**@dev.emma** (10:22):
> What kind of discrepancies are we seeing? Off by a few percent or completely wrong?

**@analytics.lead** (10:25):
> Mix of things. Here's what I've collected:
>
> 1. **CloudMetrics Corp**: Their hourly event counts are showing duplicates at hour boundaries. Raw count: 1,000,000. Aggregated count: 1,003,247.
>
> 2. **IoTSense**: Their distinct user counts are way higher than expected after merging data from multiple regions.
>
> 3. **FinanceHub**: Their histogram buckets are wrong. Values exactly at bucket boundaries are landing in the wrong bucket.

---

**@dev.alex** (10:32):
> I'll look at the boundary duplicate issue. Let me check the rolling sum logic...

**@dev.alex** (10:45):
> Found something interesting. We have a running total that's supposed to reset at window boundaries:
>
> ```javascript
> if (windowBoundary > state.windowStart) {
>   state.total = 0;
>   state.windowStart = windowBoundary;
> }
> state.total += value;
> ```
>
> But this uses `>` instead of `>=`. Events exactly at the boundary get added to the OLD window total, then the window resets, so they're not counted in the new window... wait, actually they ARE counted because the add happens after. Let me trace this again...

**@dev.alex** (10:52):
> Actually the issue is the opposite. At boundary events, the check passes (`>` is true), we reset, THEN add the value to the new window. But adjacent windows both include the boundary because of inclusive end boundaries elsewhere.

---

**@dev.emma** (11:00):
> I'm looking at the HyperLogLog merge for distinct counts. Something's definitely wrong.

**@dev.emma** (11:08):
> Found it. When merging two HLL structures, we're doing:
> ```javascript
> merged[i] = hll1[i] + hll2[i];
> ```
>
> But HLL merge should use MAX, not addition:
> ```javascript
> merged[i] = Math.max(hll1[i], hll2[i]);
> ```
>
> Addition inflates the cardinality estimate by roughly 2x when merging equal-sized HLLs.

**@analytics.lead** (11:15):
> That explains IoTSense's issue. They merge regional data and get wildly inflated distinct counts.

---

**@dev.jordan** (11:20):
> Looking at the histogram bucket issue. Here's the bucketing code:
>
> ```javascript
> for (let i = 0; i < buckets.length; i++) {
>   if (value < buckets[i]) {
>     counts[i]++;
>     placed = true;
>     break;
>   }
> }
> ```
>
> See the problem? It uses `<` instead of `<=`. So a value of exactly 10.0 with a bucket boundary at 10.0 falls through to the NEXT bucket.

**@dev.emma** (11:25):
> Classic off-by-one. P99 latency histograms would be especially wrong because boundary values are common.

---

**@sre.kim** (11:30):
> I'm seeing another issue in our billing reports. The rolling sums for high-volume customers are showing weird negative numbers sometimes.

**@dev.alex** (11:35):
> Negative sums? Let me check for overflow...

**@dev.alex** (11:42):
> Yep. We're using regular JavaScript numbers for rolling sums:
> ```javascript
> const newSum = current + value;
> ```
>
> No overflow check. For customers ingesting billions of events, we exceed `Number.MAX_SAFE_INTEGER` (2^53). After that, precision is lost and arithmetic behaves unpredictably.

**@dev.jordan** (11:48):
> We should use BigInt for those sums, or at least detect when we're approaching unsafe territory.

---

**@analytics.lead** (12:00):
> What about the rate calculation issues? Customer "RealTimeData" says their rate metrics sometimes show negative values.

**@dev.emma** (12:08):
> Rate calculation divides value delta by time delta:
> ```javascript
> const timeDelta = timestamp - prev.timestamp;
> const valueDelta = value - prev.value;
> return valueDelta / timeDelta * 1000;
> ```
>
> If there's clock skew between sources (common in distributed systems), `timeDelta` can be negative. Negative time delta = negative rate.

**@sre.kim** (12:15):
> We see this a lot with customers running across multiple regions with slightly unsynchronized clocks.

---

**@dev.alex** (12:20):
> One more issue - the Top-N calculation. Customers are seeing different results for "top 10 users" when they run the same query multiple times.

**@dev.jordan** (12:28):
> That's because JavaScript's `Array.sort()` isn't stable in all engines. When multiple items have the same score, their relative order can change between runs.

**@dev.emma** (12:32):
> And we don't have a secondary sort key for tie-breaking:
> ```javascript
> const sorted = [...items].sort((a, b) => {
>   return bVal - aVal;  // No tie-breaker
> });
> ```

---

## Summary of Issues Found

1. **Rolling Sum Overflow**: Values > 2^53 lose precision
2. **HyperLogLog Merge**: Uses addition instead of max, inflating cardinality
3. **Histogram Boundaries**: Uses `<` instead of `<=`, boundary values go to wrong bucket
4. **Rate Calculation Clock Skew**: Negative time deltas cause negative rates
5. **Running Total Reset**: Off-by-one at window boundaries
6. **Top-N Tie-Breaking**: Non-deterministic ordering when values are equal

## Files to Fix

- `services/aggregate/src/services/rollups.js` - All aggregation logic
- Related code in stream processing for windowed aggregations

---

**@analytics.lead** (12:45):
> Thanks team. Can we get fixes prioritized? The billing accuracy issue is especially critical - we can't charge customers incorrectly.

**@dev.emma** (12:48):
> I'll take the HLL merge and histogram bucket fixes. Should be straightforward.

**@dev.alex** (12:50):
> I'll handle the overflow and rate calculation issues.

**@dev.jordan** (12:52):
> I'll fix the Top-N tie-breaking and the running total boundary issue.

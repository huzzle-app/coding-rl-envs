# Alert Dashboard: Price Alert System Issues

## Monitoring Dashboard Export

**Time Range**: 2024-03-20 09:00 - 17:00 UTC
**System**: TradeEngine Price Alerts Service
**Status**: Degraded

---

## Active Incidents

### Incident 1: Alert Flooding

**Detected**: 09:15 UTC
**Status**: Investigating

```
[ERROR] AlertNotificationQueue depth: 847,291 (normal: < 1,000)
[ERROR] Notification delivery latency: 45 minutes (SLA: 30 seconds)
[WARNING] Worker goroutine count: 12,847 (normal: 50-100)
[WARNING] CPU usage Alert Service: 94%
```

**Symptom Description**:
Users report receiving hundreds of duplicate alert notifications for the same price target. Example from user `usr_9f8e7d6c`:

```json
{
  "alert_id": "alrt_5a4b3c2d",
  "symbol": "TSLA",
  "condition": "above",
  "target_price": 250.00,
  "notifications_sent": 347,
  "first_notification": "2024-03-20T09:15:00Z",
  "last_notification": "2024-03-20T09:45:00Z"
}
```

The stock crossed $250 once but user received 347 notifications.

---

### Incident 2: Missed Alerts

**Detected**: 11:30 UTC
**Status**: Investigating

```
[WARNING] Alert evaluation queue: backing up
[WARNING] Price updates processed: 12/sec (normal: 5,000/sec)
[INFO] Channel buffer utilization: 100%
```

**Symptom Description**:
Simultaneous with the flooding, many alerts are NOT triggering:

```sql
SELECT
    a.id,
    a.symbol,
    a.condition,
    a.price as target_price,
    p.high as actual_high,
    p.low as actual_low
FROM alerts a
JOIN daily_prices p ON a.symbol = p.symbol AND p.date = CURRENT_DATE
WHERE a.triggered = false
  AND ((a.condition = 'above' AND p.high > a.price)
    OR (a.condition = 'below' AND p.low < a.price))
LIMIT 10;
```

Results: 2,847 alerts should have triggered but didn't.

---

### Incident 3: "Crosses" Alerts Unreliable

**Detected**: 14:00 UTC
**Status**: Investigating

```
[DEBUG] crosses alert check: lastPrice=0.00, currentPrice=245.50
[DEBUG] crosses alert skipped: no last price recorded
```

**Symptom Description**:
Alerts with `condition = "crosses"` are rarely triggering:

Customer Report:
> "I set a 'crosses $240' alert for TSLA. The stock went from $235 to $245 and back to $238 multiple times today. Never got an alert."

Analysis of `crosses` alerts:
- Set this week: 1,247
- Triggered correctly: 23
- Should have triggered: ~890

---

## Metrics Time Series

### Price Channel Buffer

```
Time        | Buffer Usage | Dropped Messages
------------|--------------|------------------
09:00       | 3/10         | 0
09:15       | 10/10        | 127
09:30       | 10/10        | 4,892
10:00       | 10/10        | 23,401
10:30       | 10/10        | 45,729
11:00       | 10/10        | 89,203
```

### Alert Processing Rate

```
Time        | Alerts/sec | Latency (ms)
------------|------------|-------------
09:00       | 5,234      | 2
09:15       | 4,891      | 15
09:30       | 2,103      | 450
10:00       | 847        | 2,340
10:30       | 312        | 8,923
11:00       | 89         | 34,291
```

---

## Log Excerpts

### Alert Engine Startup

```
[INFO] Alert engine starting
[DEBUG] Loaded 45,892 active alerts
[DEBUG] Price channel buffer size: 10
[INFO] Started price processor goroutine
```

### During Incident

```
[WARN] priceChannel send blocking, price update for AAPL dropped
[WARN] priceChannel send blocking, price update for MSFT dropped
[WARN] priceChannel send blocking, price update for TSLA dropped
... (repeated 89,203 times)

[DEBUG] Processing price update for TSLA: $250.01
[DEBUG] Alert alrt_5a4b3c2d condition=above target=250.00 triggered=true
[DEBUG] Sending notification for alert alrt_5a4b3c2d
[DEBUG] Processing price update for TSLA: $250.02
[DEBUG] Alert alrt_5a4b3c2d condition=above target=250.00 triggered=true
[DEBUG] Sending notification for alert alrt_5a4b3c2d
[DEBUG] Processing price update for TSLA: $250.01
[DEBUG] Alert alrt_5a4b3c2d condition=above target=250.00 triggered=true
... (repeated hundreds of times)
```

### Race Condition Evidence

```
[DEBUG] goroutine-1: reading lastPrices[NVDA]
[DEBUG] goroutine-2: writing lastPrices[NVDA]=890.50
[DEBUG] goroutine-1: got lastPrices[NVDA]=0.00
[DEBUG] goroutine-1: crosses check skipped - no last price
```

---

## Code Path Analysis

### Alert Triggering Logic

The alert engine has three conditions:

1. **"above"**: `price > target`
2. **"below"**: `price < target`
3. **"crosses"**: `(lastPrice < target && price >= target) || (lastPrice > target && price <= target)`

### Observed Issues

1. **Duplicate notifications**: Alert's `triggered` flag appears to be read and written without synchronization. Multiple price updates can see `triggered = false` and all send notifications.

2. **Channel blocking**: The price update channel has a buffer of 10. Under high volume, sends block and messages are dropped.

3. **Crosses reliability**: The `lastPrices` map is accessed without proper synchronization. Sometimes reads return zero even after writes.

4. **Float comparison edge cases**: Alerts for exact price matches (e.g., "above $250.00") behave inconsistently. Sometimes $250.00 triggers "above $250.00", sometimes it doesn't.

---

## Customer Complaints Today

| Ticket | Issue | Symbol | Details |
|--------|-------|--------|---------|
| #4901 | Duplicate alerts | TSLA | 347 notifications for same alert |
| #4902 | Missing alert | AAPL | Set below $170, stock hit $169.50, no alert |
| #4903 | Crosses not working | NVDA | Set crosses $900, crossed 5 times, no alert |
| #4904 | Wrong trigger | SPY | "Above $500.00" triggered at exactly $500.00 |
| #4905 | Delayed alert | MSFT | 45 minute delay on above alert |

---

## Files Under Investigation

- `internal/alerts/engine.go` - Alert processing logic
- Price channel buffer sizing
- Last price tracking map
- Alert triggered flag synchronization
- Float comparison logic

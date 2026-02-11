# Incident Report: Double Charges During Flash Sale

## PagerDuty Alert

**Severity**: Critical (P1)
**Triggered**: 2024-03-08 19:42 UTC
**Acknowledged**: 2024-03-08 19:45 UTC
**Team**: Payments Platform

---

## Alert Details

```
CRITICAL: Duplicate payment records detected
Service: Payments
Environment: Production
Metric: payment_duplicate_ratio
Threshold: >0.1% for 5 minutes
Current Value: 4.7%
```

## Incident Summary

During the Taylor Swift "Eras Tour" flash sale, customers reported being charged multiple times for single ticket orders. Customer support received 847 complaints within the first 30 minutes of the sale going live.

## Timeline

**19:30 UTC** - Flash sale opens, traffic spikes to 15,000 requests/second

**19:35 UTC** - Payment gateway starts returning intermittent timeouts (503s)

**19:42 UTC** - Monitoring detects abnormal duplicate payment ratio

**19:48 UTC** - First customer tweet: "EventHorizon charged my card 3 times for the same order!!!"

**19:55 UTC** - CS escalates - over 200 tickets opened about duplicate charges

**20:15 UTC** - Finance confirms $2.3M in duplicate charges across 4,200 orders

## Customer Reports

### Support Ticket #48291

> I tried to buy 2 tickets for the Chicago show. The page showed "Processing..." for about 30 seconds, then showed an error "Payment failed, please try again." I clicked the button two more times and each time it showed the same error. Then I got 3 confirmation emails and my credit card shows 3 charges of $487.50 each!

### Support Ticket #48305

> Your site charged me twice. I only see one order in my account but my bank shows two pending charges. This is unacceptable.

### Twitter @angry_customer_42

> @EventHorizon HOW is your payment system this broken?! Charged me 4 TIMES for tickets I'm not even sure I got. Fix this NOW.

---

## System Observations

### Payment Service Metrics

```
Time Window: 19:30-20:00 UTC

Payment Attempts:      127,493
Successful Payments:   89,247
Timeout Errors:        38,246 (30%)
Duplicate Payments:    4,189 (4.7% of successful)

Retry Metrics:
- First attempt success: 69.4%
- Second attempt success: 22.1%
- Third attempt success: 8.5%
- Average retries per order: 2.3
```

### Payment Gateway Response Times

```
p50: 245ms
p90: 1,847ms
p99: 8,432ms (exceeds 5s timeout)
```

### Error Logs

```
2024-03-08T19:42:18Z WARN  Payment timeout orderId=ORD-7f2a3b paymentId=PAY-new amount=487.50
2024-03-08T19:42:18Z INFO  Retrying payment orderId=ORD-7f2a3b attempt=2
2024-03-08T19:42:21Z INFO  Payment successful orderId=ORD-7f2a3b paymentId=PAY-8c4d2e amount=487.50
2024-03-08T19:42:21Z INFO  Retrying payment orderId=ORD-7f2a3b attempt=3  <-- WHY?
2024-03-08T19:42:24Z INFO  Payment successful orderId=ORD-7f2a3b paymentId=PAY-9f5e3a amount=487.50
```

Note: The third retry happened even though attempt 2 succeeded. Different payment IDs were generated each time.

---

## Database Analysis

```sql
-- Duplicate payment detection query
SELECT order_id, COUNT(*) as payment_count, SUM(amount) as total_charged
FROM payments
WHERE created_at BETWEEN '2024-03-08 19:30:00' AND '2024-03-08 20:30:00'
  AND status = 'completed'
GROUP BY order_id
HAVING COUNT(*) > 1
ORDER BY payment_count DESC;
```

Results:
```
| order_id     | payment_count | total_charged |
|--------------|---------------|---------------|
| ORD-a1b2c3   | 4             | 1,950.00      |
| ORD-d4e5f6   | 3             | 1,462.50      |
| ORD-g7h8i9   | 3             | 731.25        |
| ...          | ...           | ...           |
| (4,189 rows with duplicates)                  |
```

---

## Polly Retry Policy Configuration

From `appsettings.json`:
```json
{
  "PaymentRetry": {
    "MaxRetries": 3,
    "InitialBackoff": "00:00:01",
    "MaxBackoff": "00:00:30"
  }
}
```

The retry policy is configured to retry up to 3 times on transient failures including `TimeoutException`.

---

## Questions for Investigation

1. Why do retries continue after a successful payment?
2. Why are different payment IDs generated for the same order on retry?
3. Is there any idempotency mechanism to prevent duplicate charges?
4. How does the payment service know if a previous attempt actually succeeded vs timed out?

## Root Cause Hypotheses

1. **Missing idempotency key**: Each retry creates a new payment record instead of reusing the same transaction
2. **Race condition**: Retry fires before success response is processed
3. **Timeout mismatch**: Gateway timeout longer than client timeout, so client retries while gateway is still processing

---

## Immediate Actions Taken

1. **20:30 UTC** - Disabled retry policy (set MaxRetries=0) to stop bleeding
2. **21:00 UTC** - Finance team initiated bulk refund process for duplicates
3. **21:15 UTC** - Customer communication drafted and sent

## Financial Impact

- Duplicate charges: $2,341,625.00
- Estimated refund processing fees: $23,416.25
- Customer goodwill credits issued: $125,000.00
- Reputational damage: Incalculable

---

## Services to Investigate

- `Payments` - Payment processing and retry logic
- `Orders` - Order saga coordination

## Related Configuration

- Polly retry policies
- Payment gateway timeout settings
- Circuit breaker configuration

---

**Status**: ROOT CAUSE ANALYSIS IN PROGRESS
**Assigned**: @payments-team
**Post-Mortem**: Scheduled for 2024-03-11 14:00 UTC

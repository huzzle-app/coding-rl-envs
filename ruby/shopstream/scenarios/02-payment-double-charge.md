# Customer Escalation: Double Charges and Missing Refunds

## Zendesk Ticket #89234

**Priority**: Urgent
**Customer**: Multiple (Pattern Detected)
**Created**: 2024-02-08 16:45 UTC
**Status**: Escalated to Engineering
**CSM**: Rachel Torres

---

## Pattern Analysis

Customer support has identified a pattern of payment issues affecting approximately 2.3% of orders over the past week. Three distinct issues have been reported:

### Issue 1: Double Charges

**Affected Customers**: 34 confirmed cases
**Total Overcharged**: $8,247.82

> "I was charged twice for order #ORD-445566. My credit card shows two charges of $89.99. I want my money back!" - Customer Sarah M.

> "Order confirmation shows $156.00 but my bank statement shows $312.00 was charged." - Customer James K.

### Issue 2: Refund Amount Miscalculation

**Affected Customers**: 18 confirmed cases
**Underpaid Refunds**: $1,892.43 total

> "I returned all items from my $200 order but only received a $184.67 refund. Where is the rest of my money?" - Customer Lisa P.

> "My refund was supposed to be $45.99 but I only got $42.31 back. This is theft!" - Customer Mike R.

### Issue 3: Currency Display Mismatch

**Affected Customers**: 12 confirmed cases (International)

> "Website showed $50 USD but I was charged $52.37. I know exchange rates but this is wrong." - Customer Hans G. (Germany)

---

## Technical Investigation

### Payment Service Logs

```
2024-02-08T14:23:45.123Z [PAYMENT] Processing payment for order ORD-445566
2024-02-08T14:23:45.234Z [PAYMENT] Initiating charge: $89.99 USD
2024-02-08T14:23:45.567Z [PAYMENT] Gateway timeout, retrying...
2024-02-08T14:23:46.234Z [PAYMENT] Initiating charge: $89.99 USD
2024-02-08T14:23:46.445Z [PAYMENT] Charge successful: txn_abc123
2024-02-08T14:23:46.890Z [PAYMENT] Previous retry also succeeded: txn_xyz789
# Both charges went through due to retry without idempotency check
```

### Refund Service Logs

```
2024-02-08T15:12:33.001Z [REFUND] Calculating refund for order ORD-778899
2024-02-08T15:12:33.002Z [REFUND] Original total: 199.99
2024-02-08T15:12:33.003Z [REFUND] Tax paid: 15.32
2024-02-08T15:12:33.004Z [REFUND] Shipping: 8.99
2024-02-08T15:12:33.005Z [REFUND] Subtotal: 175.68
2024-02-08T15:12:33.010Z [REFUND] Refund amount calculated: 184.67
# Expected: 199.99 (full refund for full return)
# Note: Calculation appears to have rounding/precision issues
```

### Currency Service Logs

```
2024-02-08T16:45:22.111Z [CURRENCY] Converting $50.00 USD to EUR
2024-02-08T16:45:22.112Z [CURRENCY] Rate fetch started
2024-02-08T16:45:22.115Z [CURRENCY] Rate fetch completed: 0.92 EUR/USD
2024-02-08T16:45:22.116Z [CURRENCY] Concurrent rate update detected
2024-02-08T16:45:22.117Z [CURRENCY] Using rate: 0.89 EUR/USD (stale)
# Race condition: rate changed mid-calculation
```

---

## Slack Thread: #payments-oncall

**@dev.payments** (16:50):
> Getting a lot of double charge complaints today. Checking the retry logic in payment processor.

**@dev.payments** (17:05):
> Found it - when gateway times out, we retry but don't check if the original charge actually went through. Both charges can succeed.

**@dev.backend** (17:10):
> Similar pattern in refunds. The refund calculation uses floating point arithmetic for money. We're getting precision errors that compound with multiple line items.

**@dev.payments** (17:15):
> Also seeing that currency conversion has race conditions. Two requests hitting the rate service simultaneously can use different rates.

**@qa.lead** (17:20):
> I think our tests pass because they run sequentially. Under concurrent load, these race conditions manifest.

**@dev.backend** (17:25):
> Just checked - we're using `Float` for prices throughout. Should probably be `BigDecimal`. Also the refund service calculates `subtotal + tax + shipping` separately with rounding at each step.

---

## Financial Impact Analysis

| Issue | Cases | Total Impact | Avg per Case |
|-------|-------|--------------|--------------|
| Double Charges | 34 | $8,247.82 | $242.58 |
| Short Refunds | 18 | $1,892.43 | $105.13 |
| Currency Errors | 12 | $312.67 | $26.06 |
| **Total** | **64** | **$10,452.92** | |

## Reproduction Steps

### Double Charge
1. Create an order with slow payment gateway (inject 2s latency)
2. Submit payment - first attempt times out at application level
3. Application retries automatically
4. Both gateway calls succeed - customer charged twice

### Refund Calculation Error
1. Create order with multiple items: $19.99 + $29.99 + $49.99
2. Apply 10% discount
3. Add tax (8.25%)
4. Request full refund
5. Observe refund amount is $0.50 - $2.00 less than original charge

### Currency Race
1. Set up two concurrent checkout sessions for international customer
2. Have currency rate update mid-checkout
3. Display price uses old rate, charge uses new rate (or vice versa)

---

## Files to Investigate

Based on the symptoms:
- `payments/services/payment_processor.rb` - Double charge retry logic
- `payments/services/refund_service.rb` - Refund calculation
- `payments/services/currency_service.rb` - Race conditions
- `orders/services/pricing_service.rb` - Float precision issues
- `orders/services/tax_calculator.rb` - Rounding errors

---

**Assigned**: @payments-team, @orders-team
**Deadline**: 2024-02-09 EOD
**Customer Communications**: On hold pending engineering fix

package com.helixops.billing

import org.junit.jupiter.api.Test
import java.math.BigDecimal
import java.math.RoundingMode
import kotlin.test.assertEquals
import kotlin.test.assertTrue
import kotlin.test.assertNotNull
import kotlin.test.assertFalse
import kotlin.test.assertFailsWith

/**
 * Tests for BillingService: invoicing, pricing, payments.
 *
 * Bug-specific tests:
 *   B5 - BigDecimal? NPE: nullable BigDecimal passed to add()/subtract()
 *   C6 - copy() computed field: Invoice.total not recomputed after copy(lineItems=...)
 *   E5 - batchInsert OOM: flatMap materializes entire list in memory
 *   E6 - isolation level: default READ_COMMITTED allows lost updates in transfers
 *   K5 - BigDecimal extension: applyTax adds rate instead of multiplying
 */
class BillingTests {

    // =========================================================================
    // B5: BigDecimal? NPE -- nullable BigDecimal arithmetic
    // =========================================================================

    @Test
    fun test_bigdecimal_null_check() {
        
        val service = BillingServiceFixture()
        // Customer with no overage and no discount -- both return null
        val bill = service.calculateMonthlyBill("customer-no-extras")

        assertNotNull(bill, "Monthly bill should be computed even when overage/discount are null")
        assertEquals(
            BigDecimal("29.99"),
            bill,
            "Bill should equal base plan when overage and discount are null"
        )
    }

    @Test
    fun test_no_balance_returns_zero() {
        
        val service = BillingServiceFixture()
        // overage is null, discount is null
        val result = try {
            service.calculateMonthlyBill("customer-null")
            true
        } catch (e: NullPointerException) {
            false 
        }

        assertTrue(
            result,
            "Calculating bill should not throw NullPointerException when overage/discount are null"
        )
    }

    // =========================================================================
    // C6: copy() doesn't recompute Invoice.total
    // =========================================================================

    @Test
    fun test_invoice_copy_recalculates() {
        
        // When copy(lineItems = newItems) is called, the total is NOT recomputed --
        // it retains the value from the original invoice.
        val original = InvoiceFixture(
            id = "inv1",
            customerId = "c1",
            lineItems = listOf(LineItemFixture("Widget", BigDecimal("10.00")))
        )
        assertEquals(BigDecimal("10.00"), original.total, "Original total should be 10.00")

        val updated = original.copy(
            lineItems = listOf(
                LineItemFixture("Widget", BigDecimal("10.00")),
                LineItemFixture("Gadget", BigDecimal("20.00"))
            )
        )

        
        assertEquals(
            BigDecimal("30.00"),
            updated.total,
            "Total should be recomputed after copy() with new line items"
        )
    }

    @Test
    fun test_total_consistent_after_copy() {
        
        val items = listOf(
            LineItemFixture("A", BigDecimal("5.50")),
            LineItemFixture("B", BigDecimal("3.25")),
            LineItemFixture("C", BigDecimal("1.25"))
        )
        val invoice = InvoiceFixture("inv2", "c2", items)
        val copy = invoice.copy(
            lineItems = listOf(LineItemFixture("X", BigDecimal("100.00")))
        )

        
        assertEquals(
            copy.lineItems.sumOf { it.amount },
            copy.total,
            "Invoice total must always equal sum of line items"
        )
    }

    // =========================================================================
    // E5: batchInsert OOM -- all items materialized in memory
    // =========================================================================

    @Test
    fun test_batch_insert_no_returning() {
        
        // should use chunked processing instead.
        val service = BatchInsertFixture()
        val invoices = List(10_000) { i ->
            InvoiceFixture("inv-$i", "c-$i", listOf(LineItemFixture("item", BigDecimal("1.00"))))
        }

        val strategy = service.getInsertStrategy(invoices)
        assertTrue(
            strategy.isChunked,
            "Bulk insert should use chunked processing, not materialize all items at once"
        )
    }

    @Test
    fun test_large_batch_no_oom() {
        
        // massive list that can cause OutOfMemoryError.
        val service = BatchInsertFixture()
        val invoices = List(50_000) { i ->
            InvoiceFixture("inv-$i", "c-$i", listOf(
                LineItemFixture("a", BigDecimal("1.00")),
                LineItemFixture("b", BigDecimal("2.00"))
            ))
        }

        val strategy = service.getInsertStrategy(invoices)
        assertTrue(
            strategy.maxBatchSize <= 5000,
            "Batch size should be bounded to prevent OOM, but was ${strategy.maxBatchSize}"
        )
    }

    // =========================================================================
    // E6: Transaction isolation level -- default allows lost updates
    // =========================================================================

    @Test
    fun test_isolation_level_correct() {
        
        // TOCTOU race conditions on balance reads/writes.
        val service = TransferServiceFixture()
        val isolation = service.getTransferIsolationLevel()

        assertTrue(
            isolation == "SERIALIZABLE" || isolation == "REPEATABLE_READ",
            "Financial transfers should use SERIALIZABLE or REPEATABLE_READ, but got: $isolation"
        )
    }

    @Test
    fun test_lock_held_in_transaction() {
        
        // both succeed, resulting in a negative balance (lost update).
        val service = TransferServiceFixture()
        service.setBalance("alice", BigDecimal("100.00"))
        service.setBalance("bob", BigDecimal("50.00"))

        // Simulate two concurrent transfers from Alice
        val results = service.simulateConcurrentTransfers(
            from = "alice",
            to1 = "bob", amount1 = BigDecimal("80.00"),
            to2 = "bob", amount2 = BigDecimal("80.00")
        )

        // At most one should succeed (Alice only has 100)
        assertFalse(
            results.bothSucceeded,
            "Both concurrent transfers should not succeed -- only 100 available"
        )
    }

    // =========================================================================
    // K5: BigDecimal extension -- applyTax adds rate instead of multiplying
    // =========================================================================

    @Test
    fun test_bigdecimal_rounding_explicit() {
        
        // For amount = 100 and rate = 0.10, result should be 110.00, not 100.10
        val amount = BigDecimal("100.00")
        val rate = BigDecimal("0.10")

        val service = TaxServiceFixture()
        val result = service.applyTax(amount, rate)

        assertEquals(
            BigDecimal("110.00"),
            result,
            "100.00 with 10% tax should be 110.00, not ${result}"
        )
    }

    @Test
    fun test_extension_correct_scale() {
        
        val amount = BigDecimal("50.00")
        val rate = BigDecimal("0.20")

        val service = TaxServiceFixture()
        val result = service.applyTax(amount, rate)

        // Correct: 50 * 1.20 = 60.00
        
        assertNotNull(result)
        assertTrue(
            result > BigDecimal("55.00"),
            "Tax on 50.00 at 20% should be well above 55.00, but got $result"
        )
        assertEquals(
            BigDecimal("60.00"),
            result,
            "50.00 with 20% tax should be 60.00"
        )
    }

    // =========================================================================
    // Baseline: invoicing, pricing, payments
    // =========================================================================

    @Test
    fun test_invoice_creation() {
        val invoice = InvoiceFixture(
            id = "inv1",
            customerId = "c1",
            lineItems = listOf(
                LineItemFixture("Widget", BigDecimal("25.00")),
                LineItemFixture("Gadget", BigDecimal("15.00"))
            )
        )
        assertEquals("inv1", invoice.id)
        assertEquals(2, invoice.lineItems.size)
        assertEquals(BigDecimal("40.00"), invoice.total)
    }

    @Test
    fun test_empty_invoice_total_zero() {
        val invoice = InvoiceFixture("inv-empty", "c1", emptyList())
        assertEquals(BigDecimal.ZERO, invoice.total, "Empty invoice total should be zero")
    }

    @Test
    fun test_line_item_default_quantity() {
        val item = LineItemFixture("Test", BigDecimal("10.00"))
        assertEquals(1, item.quantity, "Default quantity should be 1")
    }

    @Test
    fun test_invoice_currency_default_usd() {
        val invoice = InvoiceFixture("inv1", "c1", emptyList())
        assertEquals("USD", invoice.currency, "Default currency should be USD")
    }

    @Test
    fun test_big_decimal_scale() {
        val amount = BigDecimal("10.005").setScale(2, RoundingMode.HALF_UP)
        assertEquals(BigDecimal("10.01"), amount, "Rounding HALF_UP should round 10.005 to 10.01")
    }

    @Test
    fun test_transfer_sufficient_balance() {
        val service = TransferServiceFixture()
        service.setBalance("alice", BigDecimal("100.00"))
        service.setBalance("bob", BigDecimal("0.00"))
        val success = service.transfer("alice", "bob", BigDecimal("50.00"))
        assertTrue(success, "Transfer should succeed with sufficient balance")
    }

    @Test
    fun test_transfer_insufficient_balance() {
        val service = TransferServiceFixture()
        service.setBalance("alice", BigDecimal("10.00"))
        service.setBalance("bob", BigDecimal("0.00"))
        val success = service.transfer("alice", "bob", BigDecimal("50.00"))
        assertFalse(success, "Transfer should fail with insufficient balance")
    }

    @Test
    fun test_invoice_total_multiple_items() {
        val items = listOf(
            LineItemFixture("A", BigDecimal("1.11")),
            LineItemFixture("B", BigDecimal("2.22")),
            LineItemFixture("C", BigDecimal("3.33"))
        )
        val invoice = InvoiceFixture("inv-multi", "c1", items)
        assertEquals(BigDecimal("6.66"), invoice.total)
    }

    @Test
    fun test_zero_tax_rate() {
        val service = TaxServiceFixture()
        val result = service.applyTax(BigDecimal("100.00"), BigDecimal("0.00"))
        assertEquals(BigDecimal("100.00"), result, "Zero tax rate should return the original amount")
    }

    @Test
    fun test_negative_discount_increases_total() {
        val basePlan = BigDecimal("29.99")
        val discount = BigDecimal("-5.00") // Negative discount = surcharge
        val total = basePlan.subtract(discount)
        assertEquals(BigDecimal("34.99"), total, "Negative discount acts as surcharge")
    }

    @Test
    fun test_single_line_item_invoice() {
        val item = LineItemFixture("Solo", BigDecimal("42.00"))
        val invoice = InvoiceFixture("inv-solo", "c1", listOf(item))
        assertEquals(BigDecimal("42.00"), invoice.total)
    }

    @Test
    fun test_large_amount_precision() {
        val amount = BigDecimal("999999999.99")
        val rate = BigDecimal("0.08")
        val expected = amount.multiply(BigDecimal.ONE.add(rate)).setScale(2, RoundingMode.HALF_UP)
        assertTrue(expected > amount, "Tax should increase the amount")
    }

    @Test
    fun test_transfer_zero_amount() {
        val service = TransferServiceFixture()
        service.setBalance("alice", BigDecimal("100.00"))
        service.setBalance("bob", BigDecimal("50.00"))
        val success = service.transfer("alice", "bob", BigDecimal("0.00"))
        assertTrue(success, "Transferring zero should succeed")
    }

    @Test
    fun test_invoice_copy_preserves_id() {
        val invoice = InvoiceFixture("inv-orig", "c1", listOf(LineItemFixture("A", BigDecimal("5.00"))))
        val copy = invoice.copy(customerId = "c2")
        assertEquals("inv-orig", copy.id, "Copy should preserve the original ID when not changed")
        assertEquals("c2", copy.customerId, "Copy should update the specified field")
    }

    @Test
    fun test_line_item_with_quantity() {
        val item = LineItemFixture("Widget", BigDecimal("10.00"), quantity = 3)
        assertEquals(3, item.quantity, "Quantity should be stored correctly")
        assertEquals(BigDecimal("10.00"), item.amount, "Amount per unit should be preserved")
    }

    @Test
    fun test_transfer_exact_balance() {
        val service = TransferServiceFixture()
        service.setBalance("alice", BigDecimal("50.00"))
        service.setBalance("bob", BigDecimal("0.00"))
        val success = service.transfer("alice", "bob", BigDecimal("50.00"))
        assertTrue(success, "Transfer of exact balance should succeed")
    }

    @Test
    fun test_transfer_updates_both_balances() {
        val service = TransferServiceFixture()
        service.setBalance("alice", BigDecimal("100.00"))
        service.setBalance("bob", BigDecimal("25.00"))
        service.transfer("alice", "bob", BigDecimal("30.00"))
        // We can't directly check balances here, but we verify a second transfer works
        val success = service.transfer("alice", "bob", BigDecimal("70.00"))
        assertTrue(success, "Second transfer should succeed as alice had 70 remaining")
    }

    @Test
    fun test_invoice_with_many_items() {
        val items = (1..100).map { LineItemFixture("Item $it", BigDecimal("1.00")) }
        val invoice = InvoiceFixture("inv-large", "c1", items)
        assertEquals(BigDecimal("100.00"), invoice.total, "Invoice with 100 items of $1 should total $100")
    }

    @Test
    fun test_tax_on_small_amount() {
        val service = TaxServiceFixture()
        val result = service.applyTax(BigDecimal("0.01"), BigDecimal("0.10"))
        assertNotNull(result)
        assertTrue(result >= BigDecimal("0.01"), "Tax on 0.01 should still be at least 0.01")
    }

    @Test
    fun test_invoice_currency_custom() {
        val invoice = InvoiceFixture("inv1", "c1", emptyList(), currency = "EUR")
        assertEquals("EUR", invoice.currency, "Custom currency should be preserved")
    }

    @Test
    fun test_big_decimal_subtract_precision() {
        val a = BigDecimal("100.10")
        val b = BigDecimal("0.03")
        val result = a.subtract(b)
        assertEquals(BigDecimal("100.07"), result, "BigDecimal subtraction should maintain precision")
    }

    @Test
    fun test_transfer_from_unknown_account() {
        val service = TransferServiceFixture()
        service.setBalance("bob", BigDecimal("50.00"))
        val success = service.transfer("unknown", "bob", BigDecimal("10.00"))
        assertFalse(success, "Transfer from unknown account (zero balance) should fail")
    }

    // =========================================================================
    // Deterministic fixtures mirroring buggy production paths
    // =========================================================================

    data class LineItemFixture(
        val description: String,
        val amount: BigDecimal,
        val quantity: Int = 1
    )

    data class InvoiceFixture(
        val id: String,
        val customerId: String,
        val lineItems: List<LineItemFixture>,
        val currency: String = "USD"
    ) {
        
        val total: BigDecimal = lineItems.sumOf { it.amount }
    }

    class BillingServiceFixture {
        private val subscriptions = mutableMapOf<String, BigDecimal?>()

        fun calculateMonthlyBill(customerId: String): BigDecimal {
            val basePlan = BigDecimal("29.99")
            val overage: BigDecimal? = subscriptions[customerId]  // null if no overage
            val discount: BigDecimal? = null                       // null if no discount

            
            val subtotal = basePlan.add(overage)     
            val total = subtotal.subtract(discount)  
            return total.setScale(2, RoundingMode.HALF_UP)
        }
    }

    data class InsertStrategy(val isChunked: Boolean, val maxBatchSize: Int)

    class BatchInsertFixture {
        fun getInsertStrategy(invoices: List<InvoiceFixture>): InsertStrategy {
            
            val totalItems = invoices.sumOf { it.lineItems.size }
            return InsertStrategy(
                isChunked = false,           
                maxBatchSize = totalItems     
            )
        }
    }

    data class ConcurrentTransferResult(val bothSucceeded: Boolean)

    class TransferServiceFixture {
        private val balances = mutableMapOf<String, BigDecimal>()

        fun setBalance(customer: String, amount: BigDecimal) {
            balances[customer] = amount
        }

        fun getTransferIsolationLevel(): String {
            
            return "READ_COMMITTED" 
        }

        fun transfer(from: String, to: String, amount: BigDecimal): Boolean {
            val fromBalance = balances[from] ?: BigDecimal.ZERO
            if (fromBalance >= amount) {
                balances[from] = fromBalance - amount
                balances[to] = (balances[to] ?: BigDecimal.ZERO) + amount
                return true
            }
            return false
        }

        fun simulateConcurrentTransfers(
            from: String,
            to1: String, amount1: BigDecimal,
            to2: String, amount2: BigDecimal
        ): ConcurrentTransferResult {
            
            val balance = balances[from] ?: BigDecimal.ZERO
            val t1Success = balance >= amount1
            val t2Success = balance >= amount2
            
            return ConcurrentTransferResult(bothSucceeded = t1Success && t2Success)
        }
    }

    class TaxServiceFixture {
        fun applyTax(amount: BigDecimal, rate: BigDecimal): BigDecimal {

            return amount.add(rate).setScale(2, RoundingMode.HALF_UP)
            // Should be: amount.multiply(BigDecimal.ONE.add(rate)).setScale(2, RoundingMode.HALF_UP)
        }
    }

    // =========================================================================
    // Domain Logic: Payment allocation with partial invoice coverage
    // =========================================================================

    @Test
    fun test_partial_payment_allocates_correct_amount() {
        val fixture = PaymentAllocationFixture()
        val invoices = listOf(
            OutstandingInvoiceFixture("inv-1", BigDecimal("50.00"), 1000L)
        )
        val result = fixture.allocatePayment(invoices, BigDecimal("30.00"))
        assertEquals(BigDecimal("30.00"), result["inv-1"],
            "Partial payment should allocate only the payment amount, not the full invoice")
    }

    @Test
    fun test_payment_spans_multiple_invoices_with_remainder() {
        val fixture = PaymentAllocationFixture()
        val invoices = listOf(
            OutstandingInvoiceFixture("inv-1", BigDecimal("40.00"), 1000L),
            OutstandingInvoiceFixture("inv-2", BigDecimal("60.00"), 2000L)
        )
        val result = fixture.allocatePayment(invoices, BigDecimal("70.00"))
        assertEquals(BigDecimal("40.00"), result["inv-1"],
            "First invoice should be fully covered")
        assertEquals(BigDecimal("30.00"), result["inv-2"],
            "Second invoice should get remainder of payment")
    }

    @Test
    fun test_payment_covers_all_invoices_exactly() {
        val fixture = PaymentAllocationFixture()
        val invoices = listOf(
            OutstandingInvoiceFixture("inv-1", BigDecimal("25.00"), 1000L),
            OutstandingInvoiceFixture("inv-2", BigDecimal("25.00"), 2000L)
        )
        val result = fixture.allocatePayment(invoices, BigDecimal("50.00"))
        assertEquals(BigDecimal("25.00"), result["inv-1"])
        assertEquals(BigDecimal("25.00"), result["inv-2"])
    }

    // =========================================================================
    // Domain Logic: Tiered pricing applies per-tier rates
    // =========================================================================

    @Test
    fun test_tiered_pricing_applies_per_tier() {
        val fixture = TieredPricingFixture()
        val tiers = listOf(
            Pair(0, BigDecimal("1.00")),
            Pair(100, BigDecimal("0.80")),
            Pair(500, BigDecimal("0.60"))
        )
        val result = fixture.calculateTieredPricing(250, tiers)
        assertEquals(
            BigDecimal("220.00"), result,
            "Tiered pricing should apply each tier's rate separately: 100*1.00 + 150*0.80 = 220"
        )
    }

    @Test
    fun test_tiered_pricing_single_tier() {
        val fixture = TieredPricingFixture()
        val tiers = listOf(Pair(0, BigDecimal("2.00")))
        val result = fixture.calculateTieredPricing(50, tiers)
        assertEquals(BigDecimal("100.00"), result, "Single tier should apply uniformly")
    }

    @Test
    fun test_tiered_pricing_crosses_all_tiers() {
        val fixture = TieredPricingFixture()
        val tiers = listOf(
            Pair(0, BigDecimal("1.00")),
            Pair(10, BigDecimal("0.50")),
            Pair(20, BigDecimal("0.25"))
        )
        val result = fixture.calculateTieredPricing(30, tiers)
        assertEquals(
            BigDecimal("17.50"), result,
            "30 units across 3 tiers: 10*1.00 + 10*0.50 + 10*0.25 = 17.50"
        )
    }

    // =========================================================================
    // Multi-step: Compound discount order and compounding
    // =========================================================================

    @Test
    fun test_compound_discount_order() {
        val fixture = CompoundDiscountFixture()
        val subtotal = BigDecimal("200.00")
        val pctDiscounts = listOf(BigDecimal("0.10"))
        val flatDiscount = BigDecimal("10.00")
        val result = fixture.applyCompoundDiscount(subtotal, pctDiscounts, flatDiscount)
        assertEquals(
            BigDecimal("170.00"), result,
            "Percentage discounts should apply before flat discounts: 200*0.9=180, 180-10=170"
        )
    }

    @Test
    fun test_compound_discount_compounds_percentages() {
        val fixture = CompoundDiscountFixture()
        val subtotal = BigDecimal("1000.00")
        val pctDiscounts = listOf(BigDecimal("0.10"), BigDecimal("0.20"))
        val flatDiscount = BigDecimal.ZERO
        val result = fixture.applyCompoundDiscount(subtotal, pctDiscounts, flatDiscount)
        assertEquals(
            BigDecimal("720.00"), result,
            "Multiple percentage discounts should compound: 1000*0.90*0.80=720, not sum to 30%"
        )
    }

    @Test
    fun test_compound_discount_both_bugs_interact() {
        val fixture = CompoundDiscountFixture()
        val subtotal = BigDecimal("500.00")
        val pctDiscounts = listOf(BigDecimal("0.10"), BigDecimal("0.05"))
        val flatDiscount = BigDecimal("25.00")
        val result = fixture.applyCompoundDiscount(subtotal, pctDiscounts, flatDiscount)
        assertEquals(
            BigDecimal("402.50"), result,
            "Compound: 500*0.90*0.95=427.50, then 427.50-25=402.50"
        )
    }

    // =========================================================================
    // Latent: Revenue recognition cap on expired contracts
    // =========================================================================

    @Test
    fun test_revenue_caps_at_contract_total_when_expired() {
        val fixture = RevenueRecognitionFixture()
        val result = fixture.computeRevenueRecognition(
            contractTotal = BigDecimal("1000.00"),
            monthlyDelivered = listOf(BigDecimal("400.00"), BigDecimal("400.00"), BigDecimal("400.00")),
            contractExpired = true
        )
        assertEquals(BigDecimal("1000.00"), result,
            "Revenue should never exceed contract total, even for expired contracts")
    }

    @Test
    fun test_revenue_caps_at_contract_total_active() {
        val fixture = RevenueRecognitionFixture()
        val result = fixture.computeRevenueRecognition(
            contractTotal = BigDecimal("500.00"),
            monthlyDelivered = listOf(BigDecimal("200.00"), BigDecimal("200.00"), BigDecimal("200.00")),
            contractExpired = false
        )
        assertEquals(BigDecimal("500.00"), result,
            "Revenue should cap at contract total for active contracts")
    }

    @Test
    fun test_revenue_under_contract_total() {
        val fixture = RevenueRecognitionFixture()
        val result = fixture.computeRevenueRecognition(
            contractTotal = BigDecimal("1000.00"),
            monthlyDelivered = listOf(BigDecimal("100.00"), BigDecimal("200.00")),
            contractExpired = false
        )
        assertEquals(BigDecimal("300.00"), result,
            "Revenue under contract total should be the sum of deliveries")
    }

    data class OutstandingInvoiceFixture(val id: String, val amount: BigDecimal, val dueDate: Long)

    class PaymentAllocationFixture {
        fun allocatePayment(
            invoices: List<OutstandingInvoiceFixture>,
            paymentAmount: BigDecimal
        ): Map<String, BigDecimal> {
            val sorted = invoices.sortedBy { it.dueDate }
            val allocations = mutableMapOf<String, BigDecimal>()
            var remaining = paymentAmount
            for (inv in sorted) {
                if (remaining <= BigDecimal.ZERO) break
                allocations[inv.id] = inv.amount
                remaining = remaining.subtract(inv.amount)
            }
            return allocations
        }
    }

    class TieredPricingFixture {
        fun calculateTieredPricing(units: Int, tiers: List<Pair<Int, BigDecimal>>): BigDecimal {
            val sortedTiers = tiers.sortedBy { it.first }
            val applicableTier = sortedTiers.lastOrNull { units >= it.first } ?: sortedTiers.first()
            return BigDecimal(units).multiply(applicableTier.second).setScale(2, RoundingMode.HALF_UP)
        }
    }

    class CompoundDiscountFixture {
        fun applyCompoundDiscount(
            subtotal: BigDecimal,
            percentageDiscounts: List<BigDecimal>,
            flatDiscount: BigDecimal
        ): BigDecimal {
            var amount = subtotal.subtract(flatDiscount)
            val totalPct = percentageDiscounts.fold(BigDecimal.ZERO) { acc, pct -> acc.add(pct) }
            val discount = amount.multiply(totalPct)
            amount = amount.subtract(discount)
            return amount.setScale(2, RoundingMode.HALF_UP)
        }
    }

    class RevenueRecognitionFixture {
        fun computeRevenueRecognition(
            contractTotal: BigDecimal,
            monthlyDelivered: List<BigDecimal>,
            contractExpired: Boolean
        ): BigDecimal {
            var recognized = BigDecimal.ZERO
            for (delivered in monthlyDelivered) {
                recognized = recognized.add(delivered)
                if (!contractExpired && recognized > contractTotal) {
                    recognized = contractTotal
                    break
                }
            }
            return recognized.setScale(2, RoundingMode.HALF_UP)
        }
    }
}

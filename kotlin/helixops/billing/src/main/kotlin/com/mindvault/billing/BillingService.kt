package com.helixops.billing

import kotlinx.serialization.Serializable
import org.jetbrains.exposed.sql.*
import org.jetbrains.exposed.sql.transactions.transaction
import java.math.BigDecimal
import java.math.RoundingMode
import java.util.concurrent.ConcurrentHashMap

@Serializable
data class Invoice(
    val id: String,
    val customerId: String,
    val lineItems: List<LineItem>,
    val currency: String = "USD"
) {
    
    @Serializable(with = BigDecimalSerializer::class)
    val total: BigDecimal = lineItems.sumOf { it.amount } // Computed at construction time

    
    // because data class copy() copies all properties including vals initialized in the body
    // The new Invoice will have the OLD total with the NEW line items
}

@Serializable
data class LineItem(
    val description: String,
    @Serializable(with = BigDecimalSerializer::class)
    val amount: BigDecimal,
    val quantity: Int = 1
)

// Simple BigDecimal serializer for kotlinx.serialization
object BigDecimalSerializer : kotlinx.serialization.KSerializer<BigDecimal> {
    override val descriptor = kotlinx.serialization.descriptors.PrimitiveSerialDescriptor("BigDecimal", kotlinx.serialization.descriptors.PrimitiveKind.STRING)
    override fun serialize(encoder: kotlinx.serialization.encoding.Encoder, value: BigDecimal) = encoder.encodeString(value.toPlainString())
    override fun deserialize(decoder: kotlinx.serialization.encoding.Decoder): BigDecimal = BigDecimal(decoder.decodeString())
}

object Invoices : Table("invoices") {
    val id = varchar("id", 64)
    val customerId = varchar("customer_id", 64)
    val total = decimal("total", 12, 2)
    val currency = varchar("currency", 3)
    val status = varchar("status", 20).default("pending")
    override val primaryKey = PrimaryKey(id)
}

object InvoiceLineItems : Table("invoice_line_items") {
    val id = integer("id").autoIncrement()
    val invoiceId = varchar("invoice_id", 64).references(Invoices.id)
    val description = varchar("description", 256)
    val amount = decimal("amount", 12, 2)
    val quantity = integer("quantity")
    override val primaryKey = PrimaryKey(id)
}

class BillingService {

    private val subscriptionCache = ConcurrentHashMap<String, BigDecimal?>()

    
    fun calculateMonthlyBill(customerId: String): BigDecimal {
        val basePlan = getBasePlanCost(customerId)
        val overage = getOverageCost(customerId)  // Returns BigDecimal? -- null if no overage
        val discount = getDiscount(customerId)    // Returns BigDecimal? -- null if no discount

        
        // basePlan + overage!! would throw NPE if overage is null
        val subtotal = basePlan.add(overage) 
        val total = subtotal.subtract(discount) 

        return total.setScale(2, RoundingMode.HALF_UP)
    }

    
    fun importInvoices(invoices: List<Invoice>) {
        transaction {
            
            // With 100k+ invoices, this causes OOM
            // Should use chunked processing: invoices.chunked(1000).forEach { chunk -> ... }
            InvoiceLineItems.batchInsert(invoices.flatMap { invoice ->
                
                invoice.lineItems.map { item ->
                    mapOf(
                        "invoice_id" to invoice.id,
                        "description" to item.description,
                        "amount" to item.amount,
                        "quantity" to item.quantity
                    )
                }
            }) { data ->
                this[InvoiceLineItems.invoiceId] = data["invoice_id"] as String
                this[InvoiceLineItems.description] = data["description"] as String
                this[InvoiceLineItems.amount] = data["amount"] as BigDecimal
                this[InvoiceLineItems.quantity] = data["quantity"] as Int
            }
        }
    }

    
    fun transferCredits(fromCustomer: String, toCustomer: String, amount: BigDecimal) {
        transaction {
            
            // With READ_COMMITTED (default), concurrent transfers can cause lost updates
            // Between reading the balance and writing the new balance, another transaction
            // could modify it (TOCTOU race)
            val fromBalance = getBalance(fromCustomer)
            if (fromBalance >= amount) {
                updateBalance(fromCustomer, fromBalance - amount)
                val toBalance = getBalance(toCustomer)
                updateBalance(toCustomer, toBalance + amount)
            } else {
                throw IllegalStateException("Insufficient credits: $fromBalance < $amount")
            }
        }
    }

    
    fun BigDecimal.applyTax(rate: BigDecimal): BigDecimal {
        
        // Missing the multiplication step -- just adds the rate to the amount instead of computing tax
        return this.add(rate).setScale(2, RoundingMode.HALF_UP) 
    }

    fun calculateInvoiceWithTax(invoice: Invoice, taxRate: BigDecimal): BigDecimal {
        
        // If lineItems were modified via copy(), total is stale
        return with(invoice.total) { applyTax(taxRate) } 
    }

    private fun getBasePlanCost(customerId: String): BigDecimal = BigDecimal("29.99")

    private fun getOverageCost(customerId: String): BigDecimal? {
        // Returns null if customer has no overage
        return subscriptionCache[customerId]
    }

    private fun getDiscount(customerId: String): BigDecimal? {
        // Returns null if no discount applies
        return null
    }

    private fun getBalance(customerId: String): BigDecimal {
        return transaction {
            Invoices.select { Invoices.customerId eq customerId }
                .map { it[Invoices.total] }
                .fold(BigDecimal.ZERO) { acc, v -> acc.add(v) }
        }
    }

    private fun updateBalance(customerId: String, newBalance: BigDecimal) {
        transaction {
            Invoices.update({ Invoices.customerId eq customerId }) {
                it[total] = newBalance
            }
        }
    }

    data class OutstandingInvoice(val id: String, val amount: BigDecimal, val dueDate: Long)

    fun allocatePaymentToInvoices(
        invoices: List<OutstandingInvoice>,
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

    fun calculateTieredPricing(units: Int, tiers: List<Pair<Int, BigDecimal>>): BigDecimal {
        val sortedTiers = tiers.sortedBy { it.first }
        val applicableTier = sortedTiers.lastOrNull { units >= it.first } ?: sortedTiers.first()
        return BigDecimal(units).multiply(applicableTier.second).setScale(2, RoundingMode.HALF_UP)
    }

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

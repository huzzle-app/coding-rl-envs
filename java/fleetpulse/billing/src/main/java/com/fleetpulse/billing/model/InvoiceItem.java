package com.fleetpulse.billing.model;

import com.fleetpulse.shared.model.BaseEntity;
import jakarta.persistence.*;
import java.math.BigDecimal;

/**
 * InvoiceItem entity representing a single line item on an invoice.
 *
 * Each item has a description, quantity, unit price, computed total price,
 * and an optional reference to the job that generated this charge.
 */
@Entity
@Table(name = "invoice_items")
public class InvoiceItem extends BaseEntity {

    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "invoice_id")
    private Invoice invoice;

    @Column(nullable = false, length = 500)
    private String description;

    @Column(nullable = false, precision = 10, scale = 2)
    private BigDecimal quantity;

    @Column(name = "unit_price", nullable = false, precision = 15, scale = 2)
    private BigDecimal unitPrice;

    @Column(name = "total_price", nullable = false, precision = 15, scale = 2)
    private BigDecimal totalPrice;

    @Column(name = "job_id")
    private Long jobId;

    // Getters and setters
    public Invoice getInvoice() { return invoice; }
    public void setInvoice(Invoice invoice) { this.invoice = invoice; }
    public String getDescription() { return description; }
    public void setDescription(String desc) { this.description = desc; }
    public BigDecimal getQuantity() { return quantity; }
    public void setQuantity(BigDecimal qty) { this.quantity = qty; }
    public BigDecimal getUnitPrice() { return unitPrice; }
    public void setUnitPrice(BigDecimal price) { this.unitPrice = price; }
    public BigDecimal getTotalPrice() { return totalPrice; }
    public void setTotalPrice(BigDecimal price) { this.totalPrice = price; }
    public Long getJobId() { return jobId; }
    public void setJobId(Long id) { this.jobId = id; }
}

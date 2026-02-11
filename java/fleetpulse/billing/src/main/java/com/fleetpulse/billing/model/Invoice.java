package com.fleetpulse.billing.model;

import com.fleetpulse.shared.model.BaseEntity;
import jakarta.persistence.*;
import java.math.BigDecimal;
import java.time.LocalDate;
import java.util.ArrayList;
import java.util.List;

/**
 * Invoice entity representing a billing invoice for fleet services.
 *
 * Tracks invoice number, customer, line items, totals, tax, and payment status.
 * Uses optimistic locking via BaseEntity @Version for concurrent modification safety.
 */
@Entity
@Table(name = "invoices")
public class Invoice extends BaseEntity {

    @Column(name = "invoice_number", unique = true, nullable = false, length = 50)
    private String invoiceNumber;

    @Column(name = "customer_id")
    private Long customerId;

    @Column(name = "total_amount", precision = 15, scale = 2)
    private BigDecimal totalAmount = BigDecimal.ZERO;

    @Column(name = "tax_amount", precision = 15, scale = 2)
    private BigDecimal taxAmount = BigDecimal.ZERO;

    @Column(length = 50)
    private String status = "DRAFT";

    @Column(name = "due_date")
    private LocalDate dueDate;

    @Column(name = "paid_date")
    private LocalDate paidDate;

    @OneToMany(mappedBy = "invoice", cascade = CascadeType.ALL, fetch = FetchType.LAZY)
    private List<InvoiceItem> items = new ArrayList<>();

    // Getters and setters
    public String getInvoiceNumber() { return invoiceNumber; }
    public void setInvoiceNumber(String num) { this.invoiceNumber = num; }
    public Long getCustomerId() { return customerId; }
    public void setCustomerId(Long id) { this.customerId = id; }
    public BigDecimal getTotalAmount() { return totalAmount; }
    public void setTotalAmount(BigDecimal amount) { this.totalAmount = amount; }
    public BigDecimal getTaxAmount() { return taxAmount; }
    public void setTaxAmount(BigDecimal amount) { this.taxAmount = amount; }
    public String getStatus() { return status; }
    public void setStatus(String status) { this.status = status; }
    public LocalDate getDueDate() { return dueDate; }
    public void setDueDate(LocalDate date) { this.dueDate = date; }
    public LocalDate getPaidDate() { return paidDate; }
    public void setPaidDate(LocalDate date) { this.paidDate = date; }
    public List<InvoiceItem> getItems() { return items; }
    public void setItems(List<InvoiceItem> items) { this.items = items; }
}

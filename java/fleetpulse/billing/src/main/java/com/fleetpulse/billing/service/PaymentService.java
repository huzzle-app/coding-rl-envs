package com.fleetpulse.billing.service;

import com.fleetpulse.billing.model.Invoice;
import jakarta.persistence.EntityManager;
import jakarta.persistence.PersistenceContext;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;

import java.math.BigDecimal;
import java.util.List;

/**
 * Service handling payment processing for invoices.
 *
 * Bugs: E3, E4, D5
 * Categories: JPA/Persistence, Saga/Compensation
 */
@Service
public class PaymentService {

    private static final Logger log = LoggerFactory.getLogger(PaymentService.class);

    @PersistenceContext
    private EntityManager entityManager;

    /**
     * Retrieves all unpaid invoices for a customer.
     *
     * @param customerId the customer whose unpaid invoices to retrieve
     * @return list of unpaid invoices
     */
    // Bug E3: New EntityManager created from factory but never closed after query,
    // leaking one connection per call.
    // Category: JPA/Persistence
    public List<Invoice> getUnpaidInvoices(Long customerId) {
        EntityManager em = entityManager.getEntityManagerFactory().createEntityManager();
        var query = em.createQuery(
            "SELECT i FROM Invoice i WHERE i.customerId = :customerId AND i.status != 'PAID'",
            Invoice.class);
        query.setParameter("customerId", customerId);
        return query.getResultList();
    }

    /**
     * Processes a single payment against an invoice.
     *
     * @param invoiceId the invoice to pay
     * @param amount    the payment amount (must match invoice total)
     * @return true if payment succeeded, false if invoice not found or amount mismatch
     */
    // Bug E4: OptimisticLockException from @Version not caught, propagates as 500 error.
    // Category: JPA/Persistence
    public boolean processPayment(Long invoiceId, BigDecimal amount) {
        Invoice invoice = entityManager.find(Invoice.class, invoiceId);
        if (invoice == null) {
            return false;
        }

        if (invoice.getTotalAmount().compareTo(amount) != 0) {
            log.warn("Payment amount {} doesn't match invoice total {}",
                amount, invoice.getTotalAmount());
            return false;
        }

        invoice.setStatus("PAID");
        invoice.setPaidDate(java.time.LocalDate.now());

        entityManager.merge(invoice);
        return true;
    }

    /**
     * Processes payment across multiple invoices from a single payment amount.
     *
     * Invoices are paid in order until funds run out. If funds are insufficient
     * for the next invoice, processing stops.
     *
     * @param invoiceIds  the invoices to pay, in priority order
     * @param totalAmount the total payment amount available
     * @return true if all invoices were paid, false if funds were insufficient
     */
    // Bug D5: When processing multiple invoices sequentially, if funds run out
    // partway through, previously processed invoices remain marked as PAID
    // with no compensation (rollback).
    // Category: Saga/Compensation
    public boolean processMultiInvoicePayment(List<Long> invoiceIds, BigDecimal totalAmount) {
        BigDecimal remaining = totalAmount;
        int processed = 0;

        for (Long invoiceId : invoiceIds) {
            Invoice invoice = entityManager.find(Invoice.class, invoiceId);
            if (invoice == null) continue;

            BigDecimal invoiceAmount = invoice.getTotalAmount();
            if (remaining.compareTo(invoiceAmount) >= 0) {
                invoice.setStatus("PAID");
                invoice.setPaidDate(java.time.LocalDate.now());
                entityManager.merge(invoice);
                remaining = remaining.subtract(invoiceAmount);
                processed++;
            } else {
                // Previous invoices are marked PAID but the total payment is incomplete.
                // This leaves the system in an inconsistent state.
                log.error("Insufficient funds for invoice {}. Processed {} of {} invoices.",
                    invoiceId, processed, invoiceIds.size());
                return false;
            }
        }
        return true;
    }
}

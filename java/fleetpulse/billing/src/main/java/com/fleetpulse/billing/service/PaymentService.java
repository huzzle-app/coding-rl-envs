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
 * Contains intentional bugs:
 *   E3 - Connection pool exhaustion (EntityManager not closed)
 *   E4 - Optimistic locking not handled (OptimisticLockException uncaught)
 *   D5 - Saga compensation failure (partial payment with no rollback)
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
    
    // A new EntityManager is created from the factory but never closed after
    // the query executes. Each call leaks one connection. Under sustained load
    // the connection pool is exhausted and the application hangs.
    // Fix: Use Spring-managed queries (e.g., @PersistenceContext EntityManager
    //       directly, or a Spring Data repository), or close the EntityManager
    //       in a finally block:
    //   EntityManager em = entityManager.getEntityManagerFactory().createEntityManager();
    //   try { ... return query.getResultList(); } finally { em.close(); }
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
    
    // The Invoice entity inherits @Version from BaseEntity, so concurrent
    // modifications cause Jakarta's OptimisticLockException. This method does
    // not catch that exception, so it propagates as a 500 Internal Server Error
    // instead of returning a proper conflict response.
    // Fix: Catch OptimisticLockException and return a conflict indicator:
    //   try { entityManager.merge(invoice); }
    //   catch (OptimisticLockException e) {
    //       log.warn("Concurrent modification on invoice {}", invoiceId);
    //       return false;
    //   }
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

        
        // happened, this throws and returns 500 instead of a conflict response
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
    
    // When processing multiple invoices sequentially, if funds run out partway
    // through, the already-processed invoices remain marked as PAID even though
    // the overall multi-invoice payment is incomplete. No compensation (rollback)
    // is triggered for the previously processed invoices.
    // Fix: Implement compensation logic in the failure branch:
    //   for (int i = 0; i < processed; i++) {
    //       Invoice prev = entityManager.find(Invoice.class, invoiceIds.get(i));
    //       prev.setStatus("PENDING");
    //       prev.setPaidDate(null);
    //       entityManager.merge(prev);
    //   }
    //   return false;
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

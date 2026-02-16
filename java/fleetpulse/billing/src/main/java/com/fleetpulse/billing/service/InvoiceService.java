package com.fleetpulse.billing.service;

import com.fleetpulse.billing.model.Invoice;
import com.fleetpulse.billing.model.InvoiceItem;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.util.List;

/**
 * Service for invoice creation, calculation, and billing zone management.
 *
 * Bugs: F6, F7, F8
 * Categories: Precision/Arithmetic
 */
@Service
public class InvoiceService {

    private static final Logger log = LoggerFactory.getLogger(InvoiceService.class);

    /**
     * Calculates the average price across all items on an invoice.
     *
     * @param invoice the invoice whose items to average
     * @return the average item price, rounded to 2 decimal places
     * @throws ArithmeticException when the invoice has no items (division by zero)
     */
    // Bug F6: No guard against empty items list before dividing.
    // Category: Precision/Arithmetic
    public BigDecimal calculateAverageItemPrice(Invoice invoice) {
        BigDecimal total = invoice.getItems().stream()
            .map(InvoiceItem::getTotalPrice)
            .reduce(BigDecimal.ZERO, BigDecimal::add);

        return total.divide(BigDecimal.valueOf(invoice.getItems().size()), 2, RoundingMode.HALF_UP);
    }

    /**
     * Calculates total revenue across a list of invoices.
     *
     * @param invoices the list of invoices to sum
     * @return the total revenue as a double (lossy)
     */
    // Bug F7: Converting BigDecimal to double and accumulating with += loses precision.
    // Category: Precision/Arithmetic
    public double calculateTotalRevenue(List<Invoice> invoices) {
        double total = 0.0;
        for (Invoice invoice : invoices) {
            total += invoice.getTotalAmount().doubleValue();
        }
        return total;
    }

    /**
     * Determines the billing zone based on geographic coordinates.
     *
     * @param lat latitude of the location
     * @param lng longitude of the location
     * @return a zone identifier string like "ZONE-N-E"
     */
    // Bug F8: Truncating coordinates to 2 decimal places loses approximately 1.1 km
    // of precision, causing vehicles near zone boundaries to be assigned to
    // the wrong billing zone.
    // Category: Precision/Arithmetic
    public String getBillingZone(double lat, double lng) {
        double truncatedLat = Math.floor(lat * 100) / 100;
        double truncatedLng = Math.floor(lng * 100) / 100;

        return String.format("ZONE-%s-%s",
            truncatedLat >= 0 ? "N" : "S",
            truncatedLng >= 0 ? "E" : "W");
    }

    /**
     * Calculates tax on a given amount at a given rate.
     *
     * @param amount  the pre-tax amount
     * @param taxRate the tax rate as a decimal (e.g., 0.08 for 8%)
     * @return the tax amount rounded to 2 decimal places
     */
    public BigDecimal calculateTax(BigDecimal amount, BigDecimal taxRate) {
        return amount.multiply(taxRate).setScale(2, RoundingMode.HALF_UP);
    }

    /**
     * Creates a new invoice with the given items, computing the total from line items.
     *
     * @param invoiceNumber unique invoice identifier
     * @param customerId    the customer being billed
     * @param items         the line items for this invoice
     * @return the populated Invoice (not yet persisted)
     */
    public Invoice createInvoice(String invoiceNumber, Long customerId, List<InvoiceItem> items) {
        Invoice invoice = new Invoice();
        invoice.setInvoiceNumber(invoiceNumber);
        invoice.setCustomerId(customerId);

        BigDecimal total = BigDecimal.ZERO;
        for (InvoiceItem item : items) {
            item.setInvoice(invoice);
            total = total.add(item.getTotalPrice());
        }

        invoice.setTotalAmount(total);
        invoice.setItems(items);
        return invoice;
    }
}

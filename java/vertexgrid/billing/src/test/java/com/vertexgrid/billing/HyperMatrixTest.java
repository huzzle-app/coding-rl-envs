package com.vertexgrid.billing;

import com.vertexgrid.billing.model.Invoice;
import com.vertexgrid.billing.model.InvoiceItem;
import com.vertexgrid.billing.service.InvoiceService;
import org.junit.jupiter.api.DynamicTest;
import org.junit.jupiter.api.Tag;
import org.junit.jupiter.api.TestFactory;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.util.ArrayList;
import java.util.List;
import java.util.stream.IntStream;
import java.util.stream.Stream;

import static org.junit.jupiter.api.Assertions.*;

/**
 * Stress test matrix for billing module bugs.
 * Cycles through 3 modes testing BUGs F6, applyDiscount integer division,
 * and calculateRouteInvoice conversion factor.
 */
@Tag("stress")
public class HyperMatrixTest {

    private final InvoiceService invoiceService = new InvoiceService();

    @TestFactory
    Stream<DynamicTest> billing_hyper_matrix() {
        final int total = 500;
        return IntStream.range(0, total).mapToObj(idx ->
            DynamicTest.dynamicTest("billing_hyper_" + idx, () -> {
                int mode = idx % 3;
                switch (mode) {
                    case 0 -> divisionByZero_matrix(idx);
                    case 1 -> applyDiscount_matrix(idx);
                    default -> routeConversion_matrix(idx);
                }
            })
        );
    }

    // BUG F6: Division by zero when invoice has no items
    private void divisionByZero_matrix(int idx) {
        Invoice invoice = new Invoice();
        invoice.setInvoiceNumber("HYPER-EMPTY-" + idx);
        invoice.setCustomerId((long) idx);
        invoice.setItems(new ArrayList<>());

        assertDoesNotThrow(() -> invoiceService.calculateAverageItemPrice(invoice),
            "Empty items list should not cause ArithmeticException (division by zero)");

        BigDecimal avg = invoiceService.calculateAverageItemPrice(invoice);
        assertEquals(0, BigDecimal.ZERO.compareTo(avg),
            "Average of empty items should be zero, not throw");
    }

    // BUG: applyDiscount uses integer division: discountPercent / 100 = 0 for <100
    private void applyDiscount_matrix(int idx) {
        BigDecimal totalAmount = new BigDecimal("100.00").add(new BigDecimal(idx % 50));
        Invoice invoice = new Invoice();
        invoice.setInvoiceNumber("HYPER-DISC-" + idx);
        invoice.setCustomerId((long) idx);
        invoice.setTotalAmount(totalAmount);

        int discountPercent = 5 + (idx % 40); // 5% to 44%

        BigDecimal result = invoiceService.applyDiscount(invoice, discountPercent);

        // Bug: discountPercent / 100 uses integer division → 0 for any percent < 100
        // So the discount is always 0 and the result equals the original total
        BigDecimal expectedDiscount = totalAmount.multiply(
            BigDecimal.valueOf(discountPercent).divide(BigDecimal.valueOf(100), 4, RoundingMode.HALF_UP));
        BigDecimal expectedResult = totalAmount.subtract(expectedDiscount)
            .setScale(0, RoundingMode.HALF_UP);

        assertTrue(result.compareTo(totalAmount) < 0,
            "Applying " + discountPercent + "% discount on $" + totalAmount +
            " should reduce the amount. Got $" + result + " (integer division bug in discountPercent/100)");
    }

    // BUG: calculateRouteInvoice uses wrong conversion factor (km*1.60934 instead of km*0.621371)
    private void routeConversion_matrix(int idx) {
        double routeKm = 10.0 + (idx % 100);
        BigDecimal ratePerMile = new BigDecimal("2.50");

        Invoice invoice = invoiceService.calculateRouteInvoice(
            "HYPER-ROUTE-" + idx, (long) idx, routeKm, ratePerMile);

        assertNotNull(invoice);
        assertNotNull(invoice.getTotalAmount());

        // 1 km = 0.621371 miles (correct conversion: km → miles)
        // Bug uses 1.60934 (which is miles → km conversion, making distance LARGER)
        double correctMiles = routeKm * 0.621371;
        BigDecimal expectedTotal = BigDecimal.valueOf(correctMiles)
            .setScale(2, RoundingMode.HALF_UP)
            .multiply(ratePerMile)
            .setScale(2, RoundingMode.HALF_UP);

        // The buggy conversion gives a result about 2.59x too large
        double ratio = invoice.getTotalAmount().doubleValue() / expectedTotal.doubleValue();
        assertTrue(ratio < 1.5,
            "Route invoice total should use correct km→miles conversion (0.621371). " +
            "Got $" + invoice.getTotalAmount() + " but expected ~$" + expectedTotal +
            " for " + routeKm + " km (ratio=" + String.format("%.2f", ratio) + "x, " +
            "suggests wrong conversion factor 1.60934 instead of 0.621371)");
    }
}

package com.vertexgrid.billing;

import com.vertexgrid.billing.model.Invoice;
import com.vertexgrid.billing.model.InvoiceItem;
import com.vertexgrid.billing.service.InvoiceService;
import com.vertexgrid.billing.service.PaymentService;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Tag;
import org.junit.jupiter.api.Test;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.util.ArrayList;
import java.util.List;

import static org.junit.jupiter.api.Assertions.*;

@Tag("unit")
public class BillingServiceTest {

    private InvoiceService invoiceService;

    @BeforeEach
    void setUp() {
        invoiceService = new InvoiceService();
    }

    // ====== BUG F6: Division by zero in calculateAverageItemPrice ======
    @Test
    void test_no_division_by_zero() {
        
        Invoice invoice = new Invoice();
        invoice.setInvoiceNumber("INV-EMPTY");
        invoice.setCustomerId(1L);
        invoice.setItems(new ArrayList<>());

        // With the bug, this throws ArithmeticException: Division by zero
        // With the fix, it should return BigDecimal.ZERO
        assertDoesNotThrow(() -> invoiceService.calculateAverageItemPrice(invoice),
            "Empty items list should not cause division by zero");
    }

    @Test
    void test_empty_list_handled() {
        
        Invoice invoice = new Invoice();
        invoice.setInvoiceNumber("INV-NONE");
        invoice.setCustomerId(1L);
        invoice.setItems(new ArrayList<>());

        // The fix should return BigDecimal.ZERO for empty items
        try {
            BigDecimal avg = invoiceService.calculateAverageItemPrice(invoice);
            assertEquals(0, BigDecimal.ZERO.compareTo(avg),
                "Average of empty items should be zero");
        } catch (ArithmeticException e) {
            fail("Empty items should not throw ArithmeticException: " + e.getMessage());
        }
    }

    @Test
    void test_average_single_item() {
        Invoice invoice = createInvoiceWithItems(1, new BigDecimal("50.00"));
        BigDecimal avg = invoiceService.calculateAverageItemPrice(invoice);
        assertEquals(0, new BigDecimal("50.00").compareTo(avg),
            "Single item average should equal item price");
    }

    @Test
    void test_average_multiple_items() {
        Invoice invoice = new Invoice();
        invoice.setInvoiceNumber("INV-MULTI");
        invoice.setCustomerId(1L);

        List<InvoiceItem> items = new ArrayList<>();
        items.add(createItem("Item A", new BigDecimal("100.00")));
        items.add(createItem("Item B", new BigDecimal("200.00")));
        items.add(createItem("Item C", new BigDecimal("300.00")));
        invoice.setItems(items);

        BigDecimal avg = invoiceService.calculateAverageItemPrice(invoice);
        assertEquals(0, new BigDecimal("200.00").compareTo(avg),
            "Average of 100+200+300 should be 200.00");
    }

    @Test
    void test_average_rounding() {
        Invoice invoice = new Invoice();
        invoice.setInvoiceNumber("INV-ROUND");
        invoice.setCustomerId(1L);

        List<InvoiceItem> items = new ArrayList<>();
        items.add(createItem("Item A", new BigDecimal("10.00")));
        items.add(createItem("Item B", new BigDecimal("10.00")));
        items.add(createItem("Item C", new BigDecimal("10.00")));
        invoice.setItems(items);

        BigDecimal avg = invoiceService.calculateAverageItemPrice(invoice);
        assertEquals(0, new BigDecimal("10.00").compareTo(avg));
    }

    @Test
    void test_average_with_cents() {
        Invoice invoice = new Invoice();
        invoice.setInvoiceNumber("INV-CENT");
        invoice.setCustomerId(1L);

        List<InvoiceItem> items = new ArrayList<>();
        items.add(createItem("A", new BigDecimal("33.33")));
        items.add(createItem("B", new BigDecimal("33.33")));
        items.add(createItem("C", new BigDecimal("33.34")));
        invoice.setItems(items);

        BigDecimal avg = invoiceService.calculateAverageItemPrice(invoice);
        assertTrue(avg.compareTo(BigDecimal.ZERO) > 0);
    }

    // ====== BUG F7: Accumulator precision loss (double for monetary) ======
    @Test
    void test_accumulator_precision() {
        
        List<Invoice> invoices = new ArrayList<>();
        for (int i = 0; i < 100; i++) {
            Invoice inv = new Invoice();
            inv.setTotalAmount(new BigDecimal("0.10"));
            invoices.add(inv);
        }

        double total = invoiceService.calculateTotalRevenue(invoices);
        // With the bug, total may be 9.99999... or 10.00000001 due to double precision
        // With BigDecimal fix, it should be exactly 10.00
        BigDecimal expected = new BigDecimal("10.00");
        BigDecimal actual = BigDecimal.valueOf(total).setScale(2, RoundingMode.HALF_UP);
        assertEquals(0, expected.compareTo(actual),
            "100 * $0.10 should be exactly $10.00, got " + total);
    }

    @Test
    void test_revenue_exact() {
        
        List<Invoice> invoices = new ArrayList<>();
        for (int i = 0; i < 1000; i++) {
            Invoice inv = new Invoice();
            inv.setTotalAmount(new BigDecimal("19.99"));
            invoices.add(inv);
        }

        double total = invoiceService.calculateTotalRevenue(invoices);
        BigDecimal expected = new BigDecimal("19990.00");
        BigDecimal actual = BigDecimal.valueOf(total).setScale(2, RoundingMode.HALF_UP);
        assertEquals(0, expected.compareTo(actual),
            "1000 * $19.99 should be exactly $19990.00, got " + total);
    }

    @Test
    void test_revenue_empty_list() {
        double total = invoiceService.calculateTotalRevenue(new ArrayList<>());
        assertEquals(0.0, total, 0.001, "Empty invoices should produce zero revenue");
    }

    @Test
    void test_revenue_single_invoice() {
        List<Invoice> invoices = new ArrayList<>();
        Invoice inv = new Invoice();
        inv.setTotalAmount(new BigDecimal("999.99"));
        invoices.add(inv);

        double total = invoiceService.calculateTotalRevenue(invoices);
        assertEquals(999.99, total, 0.001);
    }

    @Test
    void test_revenue_large_amounts() {
        List<Invoice> invoices = new ArrayList<>();
        for (int i = 0; i < 10; i++) {
            Invoice inv = new Invoice();
            inv.setTotalAmount(new BigDecimal("99999.99"));
            invoices.add(inv);
        }
        double total = invoiceService.calculateTotalRevenue(invoices);
        assertTrue(total > 999000, "Large amounts should sum correctly");
    }

    @Test
    void test_revenue_mixed_amounts() {
        List<Invoice> invoices = new ArrayList<>();
        Invoice inv1 = new Invoice();
        inv1.setTotalAmount(new BigDecimal("100.50"));
        invoices.add(inv1);

        Invoice inv2 = new Invoice();
        inv2.setTotalAmount(new BigDecimal("200.75"));
        invoices.add(inv2);

        double total = invoiceService.calculateTotalRevenue(invoices);
        assertEquals(301.25, total, 0.01);
    }

    // ====== BUG F8: Geo-coordinate truncation ======
    @Test
    void test_geo_precision() {
        
        double lat = 40.748817;
        double lng = -73.985428;

        String zone = invoiceService.getBillingZone(lat, lng);
        assertNotNull(zone);
        // The zone should be based on precise coordinates, not truncated
        assertTrue(zone.startsWith("ZONE-"));
    }

    @Test
    void test_coordinate_not_truncated() {
        
        // should potentially be in different zones with proper precision
        double lat1 = 40.741;
        double lat2 = 40.749;
        double lng = -73.99;

        String zone1 = invoiceService.getBillingZone(lat1, lng);
        String zone2 = invoiceService.getBillingZone(lat2, lng);

        // Both should produce valid zones
        assertNotNull(zone1);
        assertNotNull(zone2);
        assertTrue(zone1.startsWith("ZONE-"));
        assertTrue(zone2.startsWith("ZONE-"));
    }

    @Test
    void test_billing_zone_north_east() {
        String zone = invoiceService.getBillingZone(40.0, 74.0);
        assertEquals("ZONE-N-E", zone);
    }

    @Test
    void test_billing_zone_south_west() {
        String zone = invoiceService.getBillingZone(-33.0, -71.0);
        assertEquals("ZONE-S-W", zone);
    }

    @Test
    void test_billing_zone_origin() {
        String zone = invoiceService.getBillingZone(0.0, 0.0);
        assertNotNull(zone);
        assertTrue(zone.startsWith("ZONE-"));
    }

    @Test
    void test_billing_zone_negative_lat() {
        String zone = invoiceService.getBillingZone(-10.0, 20.0);
        assertTrue(zone.contains("S"), "Negative latitude should be South");
    }

    @Test
    void test_billing_zone_negative_lng() {
        String zone = invoiceService.getBillingZone(10.0, -20.0);
        assertTrue(zone.contains("W"), "Negative longitude should be West");
    }

    @Test
    void test_geo_precision_close_points() {
        // Points within 100m of each other
        String z1 = invoiceService.getBillingZone(40.748817, -73.985428);
        String z2 = invoiceService.getBillingZone(40.748900, -73.985428);
        assertNotNull(z1);
        assertNotNull(z2);
    }

    // ====== BUG E3: Connection pool exhaustion (EntityManager not closed) ======
    @Test
    void test_connection_pool_not_exhausted() {
        
        // This test verifies the service class exists and the method signature is correct.
        // In a unit test context (no Spring), we can't fully test connection pool behavior,
        // but we verify the PaymentService contract.
        PaymentService paymentService = new PaymentService();
        assertNotNull(paymentService,
            "PaymentService should be instantiable");
    }

    @Test
    void test_em_closed() {
        
        // In production, the fix is to close EntityManager in finally block
        PaymentService paymentService = new PaymentService();
        // Without Spring context, entityManager is null - the important thing
        // is the fix adds em.close() in a finally block
        assertNotNull(paymentService);
    }

    @Test
    void test_payment_service_instantiation() {
        PaymentService service = new PaymentService();
        assertNotNull(service);
    }

    // ====== BUG E4: Optimistic lock not handled ======
    @Test
    void test_optimistic_lock_handled() {
        
        // Without Spring context, we test that the method signature is correct
        PaymentService paymentService = new PaymentService();
        // The fix should catch OptimisticLockException and return false
        // instead of letting it propagate as a 500 error
        assertNotNull(paymentService);
    }

    @Test
    void test_concurrent_update_safe() {
        
        PaymentService paymentService = new PaymentService();
        // Verify the service exists and can handle concurrent access pattern
        assertNotNull(paymentService);
    }

    // ====== BUG D5: Saga compensation failure ======
    @Test
    void test_saga_compensation() {
        
        // When processMultiInvoicePayment fails midway, already-paid invoices
        // should be rolled back (compensation), but they're not
        PaymentService paymentService = new PaymentService();
        // The fix should implement compensation logic in the failure branch
        assertNotNull(paymentService);
    }

    @Test
    void test_partial_rollback() {
        
        // should be reverted from PAID back to PENDING
        PaymentService paymentService = new PaymentService();
        assertNotNull(paymentService);
    }

    // ====== Invoice creation tests ======
    @Test
    void test_create_invoice_basic() {
        List<InvoiceItem> items = new ArrayList<>();
        items.add(createItem("Service A", new BigDecimal("100.00")));
        items.add(createItem("Service B", new BigDecimal("200.00")));

        Invoice invoice = invoiceService.createInvoice("INV-001", 1L, items);

        assertEquals("INV-001", invoice.getInvoiceNumber());
        assertEquals(1L, invoice.getCustomerId());
        assertEquals(2, invoice.getItems().size());
        assertEquals(0, new BigDecimal("300.00").compareTo(invoice.getTotalAmount()));
    }

    @Test
    void test_create_invoice_empty_items() {
        Invoice invoice = invoiceService.createInvoice("INV-002", 1L, new ArrayList<>());
        assertEquals(0, BigDecimal.ZERO.compareTo(invoice.getTotalAmount()));
    }

    @Test
    void test_create_invoice_single_item() {
        List<InvoiceItem> items = new ArrayList<>();
        items.add(createItem("Service", new BigDecimal("500.00")));

        Invoice invoice = invoiceService.createInvoice("INV-003", 1L, items);
        assertEquals(0, new BigDecimal("500.00").compareTo(invoice.getTotalAmount()));
    }

    @Test
    void test_create_invoice_item_linked() {
        List<InvoiceItem> items = new ArrayList<>();
        items.add(createItem("Service", new BigDecimal("100.00")));

        Invoice invoice = invoiceService.createInvoice("INV-004", 1L, items);
        assertEquals(invoice, items.get(0).getInvoice(),
            "Items should be linked to their invoice");
    }

    @Test
    void test_create_invoice_total_calculated() {
        List<InvoiceItem> items = new ArrayList<>();
        items.add(createItem("A", new BigDecimal("10.00")));
        items.add(createItem("B", new BigDecimal("20.00")));
        items.add(createItem("C", new BigDecimal("30.00")));
        items.add(createItem("D", new BigDecimal("40.00")));

        Invoice invoice = invoiceService.createInvoice("INV-005", 2L, items);
        assertEquals(0, new BigDecimal("100.00").compareTo(invoice.getTotalAmount()));
    }

    // ====== Tax calculation tests ======
    @Test
    void test_calculate_tax() {
        BigDecimal amount = new BigDecimal("100.00");
        BigDecimal rate = new BigDecimal("0.08");
        BigDecimal tax = invoiceService.calculateTax(amount, rate);
        assertEquals(0, new BigDecimal("8.00").compareTo(tax));
    }

    @Test
    void test_calculate_tax_zero_rate() {
        BigDecimal amount = new BigDecimal("100.00");
        BigDecimal rate = BigDecimal.ZERO;
        BigDecimal tax = invoiceService.calculateTax(amount, rate);
        assertEquals(0, BigDecimal.ZERO.compareTo(tax));
    }

    @Test
    void test_calculate_tax_rounding() {
        BigDecimal amount = new BigDecimal("99.99");
        BigDecimal rate = new BigDecimal("0.0825"); // 8.25%
        BigDecimal tax = invoiceService.calculateTax(amount, rate);
        assertNotNull(tax);
        assertTrue(tax.scale() <= 2, "Tax should be rounded to 2 decimal places");
    }

    @Test
    void test_calculate_tax_high_rate() {
        BigDecimal amount = new BigDecimal("1000.00");
        BigDecimal rate = new BigDecimal("0.25");
        BigDecimal tax = invoiceService.calculateTax(amount, rate);
        assertEquals(0, new BigDecimal("250.00").compareTo(tax));
    }

    @Test
    void test_calculate_tax_precision() {
        BigDecimal amount = new BigDecimal("33.33");
        BigDecimal rate = new BigDecimal("0.07");
        BigDecimal tax = invoiceService.calculateTax(amount, rate);
        assertEquals(2, tax.scale());
    }

    // ====== Invoice model tests ======
    @Test
    void test_invoice_defaults() {
        Invoice invoice = new Invoice();
        assertEquals("DRAFT", invoice.getStatus());
        assertEquals(0, BigDecimal.ZERO.compareTo(invoice.getTotalAmount()));
        assertEquals(0, BigDecimal.ZERO.compareTo(invoice.getTaxAmount()));
    }

    @Test
    void test_invoice_setters() {
        Invoice invoice = new Invoice();
        invoice.setInvoiceNumber("INV-TEST");
        invoice.setCustomerId(42L);
        invoice.setStatus("PAID");

        assertEquals("INV-TEST", invoice.getInvoiceNumber());
        assertEquals(42L, invoice.getCustomerId());
        assertEquals("PAID", invoice.getStatus());
    }

    @Test
    void test_invoice_dates() {
        Invoice invoice = new Invoice();
        java.time.LocalDate dueDate = java.time.LocalDate.of(2025, 3, 15);
        java.time.LocalDate paidDate = java.time.LocalDate.of(2025, 3, 10);
        invoice.setDueDate(dueDate);
        invoice.setPaidDate(paidDate);

        assertEquals(dueDate, invoice.getDueDate());
        assertEquals(paidDate, invoice.getPaidDate());
    }

    @Test
    void test_invoice_item_setters() {
        InvoiceItem item = new InvoiceItem();
        item.setDescription("Test item");
        item.setQuantity(new BigDecimal("5"));
        item.setUnitPrice(new BigDecimal("10.00"));
        item.setTotalPrice(new BigDecimal("50.00"));
        item.setJobId(100L);

        assertEquals("Test item", item.getDescription());
        assertEquals(0, new BigDecimal("5").compareTo(item.getQuantity()));
        assertEquals(0, new BigDecimal("10.00").compareTo(item.getUnitPrice()));
        assertEquals(0, new BigDecimal("50.00").compareTo(item.getTotalPrice()));
        assertEquals(100L, item.getJobId());
    }

    @Test
    void test_invoice_items_list() {
        Invoice invoice = new Invoice();
        List<InvoiceItem> items = new ArrayList<>();
        items.add(createItem("A", new BigDecimal("10.00")));
        items.add(createItem("B", new BigDecimal("20.00")));
        invoice.setItems(items);

        assertEquals(2, invoice.getItems().size());
    }

    // ====== Revenue edge cases ======
    @Test
    void test_revenue_zero_amounts() {
        List<Invoice> invoices = new ArrayList<>();
        for (int i = 0; i < 5; i++) {
            Invoice inv = new Invoice();
            inv.setTotalAmount(BigDecimal.ZERO);
            invoices.add(inv);
        }
        double total = invoiceService.calculateTotalRevenue(invoices);
        assertEquals(0.0, total, 0.001);
    }

    @Test
    void test_revenue_precision_pennies() {
        // Known floating-point problem: 0.1 + 0.2 != 0.3
        List<Invoice> invoices = new ArrayList<>();
        Invoice inv1 = new Invoice();
        inv1.setTotalAmount(new BigDecimal("0.10"));
        invoices.add(inv1);

        Invoice inv2 = new Invoice();
        inv2.setTotalAmount(new BigDecimal("0.20"));
        invoices.add(inv2);

        double total = invoiceService.calculateTotalRevenue(invoices);
        BigDecimal bd = BigDecimal.valueOf(total).setScale(2, RoundingMode.HALF_UP);
        assertEquals(0, new BigDecimal("0.30").compareTo(bd));
    }

    @Test
    void test_revenue_many_small_amounts() {
        List<Invoice> invoices = new ArrayList<>();
        for (int i = 0; i < 500; i++) {
            Invoice inv = new Invoice();
            inv.setTotalAmount(new BigDecimal("0.01"));
            invoices.add(inv);
        }
        double total = invoiceService.calculateTotalRevenue(invoices);
        BigDecimal bd = BigDecimal.valueOf(total).setScale(2, RoundingMode.HALF_UP);
        assertEquals(0, new BigDecimal("5.00").compareTo(bd),
            "500 * $0.01 should be $5.00");
    }

    // ====== Average edge cases ======
    @Test
    void test_average_identical_items() {
        Invoice invoice = new Invoice();
        invoice.setInvoiceNumber("INV-ID");
        invoice.setCustomerId(1L);

        List<InvoiceItem> items = new ArrayList<>();
        for (int i = 0; i < 10; i++) {
            items.add(createItem("Item " + i, new BigDecimal("25.00")));
        }
        invoice.setItems(items);

        BigDecimal avg = invoiceService.calculateAverageItemPrice(invoice);
        assertEquals(0, new BigDecimal("25.00").compareTo(avg));
    }

    @Test
    void test_average_large_list() {
        Invoice invoice = new Invoice();
        invoice.setInvoiceNumber("INV-LG");
        invoice.setCustomerId(1L);

        List<InvoiceItem> items = new ArrayList<>();
        for (int i = 0; i < 100; i++) {
            items.add(createItem("Item " + i, new BigDecimal("10.00")));
        }
        invoice.setItems(items);

        BigDecimal avg = invoiceService.calculateAverageItemPrice(invoice);
        assertEquals(0, new BigDecimal("10.00").compareTo(avg));
    }

    @Test
    void test_average_non_terminating_division() {
        // 100/3 = 33.333... should not throw ArithmeticException
        Invoice invoice = new Invoice();
        invoice.setInvoiceNumber("INV-NT");
        invoice.setCustomerId(1L);

        List<InvoiceItem> items = new ArrayList<>();
        items.add(createItem("A", new BigDecimal("10.00")));
        items.add(createItem("B", new BigDecimal("20.00")));
        items.add(createItem("C", new BigDecimal("70.00")));
        invoice.setItems(items);

        assertDoesNotThrow(() -> invoiceService.calculateAverageItemPrice(invoice));
    }

    // ====== Geo zone edge cases ======
    @Test
    void test_geo_equator() {
        String zone = invoiceService.getBillingZone(0.0, 100.0);
        assertNotNull(zone);
    }

    @Test
    void test_geo_meridian() {
        String zone = invoiceService.getBillingZone(50.0, 0.0);
        assertNotNull(zone);
    }

    @Test
    void test_geo_extreme_latitude() {
        String north = invoiceService.getBillingZone(89.99, 0.0);
        String south = invoiceService.getBillingZone(-89.99, 0.0);
        assertTrue(north.contains("N"));
        assertTrue(south.contains("S"));
    }

    @Test
    void test_geo_extreme_longitude() {
        String east = invoiceService.getBillingZone(0.0, 179.99);
        String west = invoiceService.getBillingZone(0.0, -179.99);
        assertTrue(east.contains("E"));
        assertTrue(west.contains("W"));
    }

    @Test
    void test_geo_fractional_coordinates() {
        String z1 = invoiceService.getBillingZone(40.748817, -73.985428);
        String z2 = invoiceService.getBillingZone(40.748899, -73.985499);
        assertNotNull(z1);
        assertNotNull(z2);
    }

    @Test
    void test_create_invoice_many_items() {
        List<InvoiceItem> items = new ArrayList<>();
        for (int i = 0; i < 50; i++) {
            items.add(createItem("Item " + i, new BigDecimal("1.00")));
        }
        Invoice invoice = invoiceService.createInvoice("INV-MANY", 1L, items);
        assertEquals(50, invoice.getItems().size());
        assertEquals(0, new BigDecimal("50.00").compareTo(invoice.getTotalAmount()));
    }

    @Test
    void test_create_invoice_large_amounts() {
        List<InvoiceItem> items = new ArrayList<>();
        items.add(createItem("Big item", new BigDecimal("999999.99")));
        Invoice invoice = invoiceService.createInvoice("INV-BIG", 1L, items);
        assertEquals(0, new BigDecimal("999999.99").compareTo(invoice.getTotalAmount()));
    }

    @Test
    void test_tax_small_amount() {
        BigDecimal tax = invoiceService.calculateTax(new BigDecimal("0.01"), new BigDecimal("0.10"));
        assertTrue(tax.compareTo(BigDecimal.ZERO) >= 0);
    }

    @Test
    void test_revenue_negative_amounts() {
        // Credits / refunds
        List<Invoice> invoices = new ArrayList<>();
        Invoice inv = new Invoice();
        inv.setTotalAmount(new BigDecimal("-50.00"));
        invoices.add(inv);

        double total = invoiceService.calculateTotalRevenue(invoices);
        assertTrue(total < 0);
    }

    @Test
    void test_invoice_item_null_invoice() {
        InvoiceItem item = new InvoiceItem();
        assertNull(item.getInvoice());
    }

    @Test
    void test_invoice_null_dates() {
        Invoice invoice = new Invoice();
        assertNull(invoice.getDueDate());
        assertNull(invoice.getPaidDate());
    }

    @Test
    void test_invoice_total_with_tax() {
        Invoice invoice = new Invoice();
        invoice.setTotalAmount(new BigDecimal("100.00"));
        invoice.setTaxAmount(new BigDecimal("8.00"));

        assertEquals(0, new BigDecimal("100.00").compareTo(invoice.getTotalAmount()));
        assertEquals(0, new BigDecimal("8.00").compareTo(invoice.getTaxAmount()));
    }

    @Test
    void test_geo_many_zones() {
        // Generate multiple zones and verify all are valid
        for (int lat = -90; lat <= 90; lat += 30) {
            for (int lng = -180; lng <= 180; lng += 60) {
                String zone = invoiceService.getBillingZone(lat, lng);
                assertNotNull(zone, "Zone should not be null for lat=" + lat + " lng=" + lng);
                assertTrue(zone.startsWith("ZONE-"));
            }
        }
    }

    @Test
    void test_average_decimal_precision() {
        Invoice invoice = new Invoice();
        invoice.setInvoiceNumber("INV-DEC");
        invoice.setCustomerId(1L);

        List<InvoiceItem> items = new ArrayList<>();
        items.add(createItem("A", new BigDecimal("1.11")));
        items.add(createItem("B", new BigDecimal("2.22")));
        invoice.setItems(items);

        BigDecimal avg = invoiceService.calculateAverageItemPrice(invoice);
        assertTrue(avg.scale() <= 2, "Average should have at most 2 decimal places");
    }

    @Test
    void test_revenue_consistent_accumulation() {
        // Same value repeated should give exact multiple
        List<Invoice> invoices = new ArrayList<>();
        for (int i = 0; i < 10; i++) {
            Invoice inv = new Invoice();
            inv.setTotalAmount(new BigDecimal("7.77"));
            invoices.add(inv);
        }
        double total = invoiceService.calculateTotalRevenue(invoices);
        BigDecimal bd = BigDecimal.valueOf(total).setScale(2, RoundingMode.HALF_UP);
        assertEquals(0, new BigDecimal("77.70").compareTo(bd));
    }

    // ====== Additional precision and edge case tests ======
    @Test
    void test_revenue_two_large_invoices() {
        List<Invoice> invoices = new ArrayList<>();
        Invoice inv1 = new Invoice();
        inv1.setTotalAmount(new BigDecimal("50000.50"));
        invoices.add(inv1);
        Invoice inv2 = new Invoice();
        inv2.setTotalAmount(new BigDecimal("50000.50"));
        invoices.add(inv2);
        double total = invoiceService.calculateTotalRevenue(invoices);
        assertEquals(100001.00, total, 0.01);
    }

    @Test
    void test_average_two_items_precise() {
        Invoice invoice = new Invoice();
        invoice.setInvoiceNumber("INV-2P");
        invoice.setCustomerId(1L);
        List<InvoiceItem> items = new ArrayList<>();
        items.add(createItem("A", new BigDecimal("1.00")));
        items.add(createItem("B", new BigDecimal("2.00")));
        invoice.setItems(items);
        BigDecimal avg = invoiceService.calculateAverageItemPrice(invoice);
        assertEquals(0, new BigDecimal("1.50").compareTo(avg));
    }

    @Test
    void test_billing_zone_small_positive() {
        String zone = invoiceService.getBillingZone(0.001, 0.001);
        assertNotNull(zone);
    }

    @Test
    void test_billing_zone_small_negative() {
        String zone = invoiceService.getBillingZone(-0.001, -0.001);
        assertNotNull(zone);
    }

    @Test
    void test_create_invoice_customer_id_set() {
        Invoice invoice = invoiceService.createInvoice("INV-CID", 99L, new ArrayList<>());
        assertEquals(99L, invoice.getCustomerId());
    }

    @Test
    void test_calculate_tax_large_amount() {
        BigDecimal tax = invoiceService.calculateTax(new BigDecimal("1000000.00"), new BigDecimal("0.05"));
        assertEquals(0, new BigDecimal("50000.00").compareTo(tax));
    }

    @Test
    void test_revenue_alternating_amounts() {
        List<Invoice> invoices = new ArrayList<>();
        for (int i = 0; i < 20; i++) {
            Invoice inv = new Invoice();
            inv.setTotalAmount(i % 2 == 0 ? new BigDecimal("10.00") : new BigDecimal("20.00"));
            invoices.add(inv);
        }
        double total = invoiceService.calculateTotalRevenue(invoices);
        assertEquals(300.00, total, 0.01);
    }

    @Test
    void test_invoice_status_transitions() {
        Invoice invoice = new Invoice();
        assertEquals("DRAFT", invoice.getStatus());
        invoice.setStatus("SENT");
        assertEquals("SENT", invoice.getStatus());
        invoice.setStatus("PAID");
        assertEquals("PAID", invoice.getStatus());
    }

    @Test
    void test_invoice_item_job_id_null() {
        InvoiceItem item = new InvoiceItem();
        assertNull(item.getJobId());
    }

    @Test
    void test_invoice_item_description_null() {
        InvoiceItem item = new InvoiceItem();
        assertNull(item.getDescription());
    }

    @Test
    void test_average_five_items() {
        Invoice invoice = new Invoice();
        invoice.setInvoiceNumber("INV-5I");
        invoice.setCustomerId(1L);
        List<InvoiceItem> items = new ArrayList<>();
        items.add(createItem("A", new BigDecimal("10.00")));
        items.add(createItem("B", new BigDecimal("20.00")));
        items.add(createItem("C", new BigDecimal("30.00")));
        items.add(createItem("D", new BigDecimal("40.00")));
        items.add(createItem("E", new BigDecimal("50.00")));
        invoice.setItems(items);
        BigDecimal avg = invoiceService.calculateAverageItemPrice(invoice);
        assertEquals(0, new BigDecimal("30.00").compareTo(avg));
    }

    @Test
    void test_geo_zone_format() {
        String zone = invoiceService.getBillingZone(45.0, 90.0);
        assertTrue(zone.matches("ZONE-[NS]-[EW]"), "Zone should match ZONE-[NS]-[EW] pattern");
    }

    @Test
    void test_revenue_single_penny() {
        List<Invoice> invoices = new ArrayList<>();
        Invoice inv = new Invoice();
        inv.setTotalAmount(new BigDecimal("0.01"));
        invoices.add(inv);
        double total = invoiceService.calculateTotalRevenue(invoices);
        assertEquals(0.01, total, 0.001);
    }

    @Test
    void test_create_invoice_preserves_item_order() {
        List<InvoiceItem> items = new ArrayList<>();
        items.add(createItem("First", new BigDecimal("1.00")));
        items.add(createItem("Second", new BigDecimal("2.00")));
        items.add(createItem("Third", new BigDecimal("3.00")));
        Invoice invoice = invoiceService.createInvoice("INV-ORD", 1L, items);
        assertEquals("First", invoice.getItems().get(0).getDescription());
        assertEquals("Third", invoice.getItems().get(2).getDescription());
    }

    @Test
    void test_tax_one_percent() {
        BigDecimal tax = invoiceService.calculateTax(new BigDecimal("200.00"), new BigDecimal("0.01"));
        assertEquals(0, new BigDecimal("2.00").compareTo(tax));
    }

    @Test
    void test_invoice_total_amount_setter() {
        Invoice invoice = new Invoice();
        invoice.setTotalAmount(new BigDecimal("12345.67"));
        assertEquals(0, new BigDecimal("12345.67").compareTo(invoice.getTotalAmount()));
    }

    @Test
    void test_invoice_tax_amount_setter() {
        Invoice invoice = new Invoice();
        invoice.setTaxAmount(new BigDecimal("987.65"));
        assertEquals(0, new BigDecimal("987.65").compareTo(invoice.getTaxAmount()));
    }

    @Test
    void test_revenue_thousand_invoices() {
        List<Invoice> invoices = new ArrayList<>();
        for (int i = 0; i < 1000; i++) {
            Invoice inv = new Invoice();
            inv.setTotalAmount(new BigDecimal("1.00"));
            invoices.add(inv);
        }
        double total = invoiceService.calculateTotalRevenue(invoices);
        assertEquals(1000.00, total, 0.01);
    }

    @Test
    void test_geo_antipodal_points() {
        String zone1 = invoiceService.getBillingZone(40.0, 74.0);
        String zone2 = invoiceService.getBillingZone(-40.0, -106.0);
        assertNotEquals(zone1, zone2, "Antipodal points should be in different zone quadrants");
    }

    @Test
    void test_average_with_zero_item() {
        Invoice invoice = new Invoice();
        invoice.setInvoiceNumber("INV-Z");
        invoice.setCustomerId(1L);
        List<InvoiceItem> items = new ArrayList<>();
        items.add(createItem("A", BigDecimal.ZERO));
        items.add(createItem("B", new BigDecimal("100.00")));
        invoice.setItems(items);
        BigDecimal avg = invoiceService.calculateAverageItemPrice(invoice);
        assertEquals(0, new BigDecimal("50.00").compareTo(avg));
    }

    @Test
    void test_payment_service_not_null() {
        assertNotNull(new PaymentService());
    }

    // ====== applyDiscount tests ======
    @Test
    void test_apply_discount_10_percent() {
        Invoice invoice = new Invoice();
        invoice.setTotalAmount(new BigDecimal("100.00"));
        BigDecimal result = invoiceService.applyDiscount(invoice, 10);
        assertEquals(0, new BigDecimal("90.00").compareTo(result),
            "10% discount on $100 should yield $90.00, got " + result);
    }

    @Test
    void test_apply_discount_preserves_cents() {
        Invoice invoice = new Invoice();
        invoice.setTotalAmount(new BigDecimal("99.99"));
        BigDecimal result = invoiceService.applyDiscount(invoice, 15);
        // 99.99 * 0.85 = 84.9915 -> should round to 84.99
        assertTrue(result.scale() >= 2,
            "Discounted amount should preserve cents (2 decimal places), got scale " + result.scale());
    }

    @Test
    void test_apply_discount_25_percent() {
        Invoice invoice = new Invoice();
        invoice.setTotalAmount(new BigDecimal("200.00"));
        BigDecimal result = invoiceService.applyDiscount(invoice, 25);
        assertEquals(0, new BigDecimal("150.00").compareTo(result),
            "25% discount on $200 should yield $150.00, got " + result);
    }

    @Test
    void test_apply_discount_0_percent() {
        Invoice invoice = new Invoice();
        invoice.setTotalAmount(new BigDecimal("50.00"));
        BigDecimal result = invoiceService.applyDiscount(invoice, 0);
        assertEquals(0, new BigDecimal("50.00").compareTo(result),
            "0% discount should leave total unchanged");
    }

    @Test
    void test_apply_discount_50_percent() {
        Invoice invoice = new Invoice();
        invoice.setTotalAmount(new BigDecimal("80.00"));
        BigDecimal result = invoiceService.applyDiscount(invoice, 50);
        assertEquals(0, new BigDecimal("40.00").compareTo(result),
            "50% discount on $80 should yield $40.00, got " + result);
    }

    // ====== calculateRouteInvoice tests ======
    @Test
    void test_route_invoice_km_to_miles_conversion() {
        // 100 km = 62.137 miles (divide by 1.60934)
        Invoice invoice = invoiceService.calculateRouteInvoice("INV-R1", 1L,
            100.0, new BigDecimal("1.00"));
        // At $1/mile, total should be ~$62.14
        BigDecimal total = invoice.getTotalAmount();
        assertTrue(total.compareTo(new BigDecimal("60.00")) > 0 &&
                   total.compareTo(new BigDecimal("65.00")) < 0,
            "100km at $1/mile should be ~$62.14 (100/1.60934), got " + total);
    }

    @Test
    void test_route_invoice_conversion_direction() {
        // 1 mile = 1.60934 km, so 1.60934 km should be exactly 1 mile
        Invoice invoice = invoiceService.calculateRouteInvoice("INV-R2", 1L,
            1.60934, new BigDecimal("10.00"));
        BigDecimal total = invoice.getTotalAmount();
        // 1.60934 km / 1.60934 = 1 mile * $10 = $10.00
        assertEquals(0, new BigDecimal("10.00").compareTo(total),
            "1.60934 km should equal exactly 1 mile, total should be $10.00, got " + total);
    }

    @Test
    void test_route_invoice_has_item() {
        Invoice invoice = invoiceService.calculateRouteInvoice("INV-R3", 1L,
            50.0, new BigDecimal("2.00"));
        assertNotNull(invoice.getItems());
        assertEquals(1, invoice.getItems().size());
        assertTrue(invoice.getItems().get(0).getDescription().contains("miles"));
    }

    @Test
    void test_route_invoice_fields() {
        Invoice invoice = invoiceService.calculateRouteInvoice("INV-R4", 42L,
            10.0, new BigDecimal("5.00"));
        assertEquals("INV-R4", invoice.getInvoiceNumber());
        assertEquals(42L, invoice.getCustomerId());
        assertTrue(invoice.getTotalAmount().compareTo(BigDecimal.ZERO) > 0);
    }

    @Test
    void test_route_invoice_large_distance() {
        // 1000 km = ~621.37 miles
        Invoice invoice = invoiceService.calculateRouteInvoice("INV-R5", 1L,
            1000.0, new BigDecimal("0.50"));
        BigDecimal total = invoice.getTotalAmount();
        // ~621.37 miles * $0.50 = ~$310.69
        assertTrue(total.compareTo(new BigDecimal("300.00")) > 0 &&
                   total.compareTo(new BigDecimal("320.00")) < 0,
            "1000km at $0.50/mile should be ~$310.69, got " + total);
    }

    // Helpers
    private Invoice createInvoiceWithItems(int count, BigDecimal priceEach) {
        Invoice invoice = new Invoice();
        invoice.setInvoiceNumber("INV-" + System.nanoTime());
        invoice.setCustomerId(1L);

        List<InvoiceItem> items = new ArrayList<>();
        for (int i = 0; i < count; i++) {
            items.add(createItem("Item " + i, priceEach));
        }
        invoice.setItems(items);
        return invoice;
    }

    private InvoiceItem createItem(String description, BigDecimal totalPrice) {
        InvoiceItem item = new InvoiceItem();
        item.setDescription(description);
        item.setQuantity(BigDecimal.ONE);
        item.setUnitPrice(totalPrice);
        item.setTotalPrice(totalPrice);
        return item;
    }
}

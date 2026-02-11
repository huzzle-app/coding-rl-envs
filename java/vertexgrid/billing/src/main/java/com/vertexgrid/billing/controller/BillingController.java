package com.vertexgrid.billing.controller;

import com.vertexgrid.billing.service.InvoiceService;
import com.vertexgrid.billing.service.PaymentService;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.math.BigDecimal;
import java.util.Map;

/**
 * REST controller exposing billing endpoints for zone lookup,
 * payment processing, and health checks.
 */
@RestController
@RequestMapping("/api/billing")
public class BillingController {

    @Autowired
    private InvoiceService invoiceService;

    @Autowired
    private PaymentService paymentService;

    @GetMapping("/zone")
    public ResponseEntity<Map<String, String>> getBillingZone(
            @RequestParam double lat, @RequestParam double lng) {
        String zone = invoiceService.getBillingZone(lat, lng);
        return ResponseEntity.ok(Map.of("zone", zone));
    }

    @PostMapping("/pay/{invoiceId}")
    public ResponseEntity<Map<String, Object>> processPayment(
            @PathVariable Long invoiceId, @RequestParam String amount) {
        boolean success = paymentService.processPayment(invoiceId, new BigDecimal(amount));
        return ResponseEntity.ok(Map.of("success", success));
    }

    @GetMapping("/health")
    public ResponseEntity<Map<String, String>> health() {
        return ResponseEntity.ok(Map.of("status", "UP", "service", "billing"));
    }
}

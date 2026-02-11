package com.vertexgrid.compliance.controller;

import com.vertexgrid.compliance.service.ComplianceService;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.Map;

/**
 * REST controller exposing compliance endpoints for rate calculation
 * and health checks.
 */
@RestController
@RequestMapping("/api/compliance")
public class ComplianceController {

    @Autowired
    private ComplianceService complianceService;

    @GetMapping("/rate")
    public ResponseEntity<Map<String, Object>> getComplianceRate(
            @RequestParam int compliantDays, @RequestParam int totalDays) {
        double rate = complianceService.calculateComplianceRate(compliantDays, totalDays);
        return ResponseEntity.ok(Map.of("complianceRate", rate));
    }

    @GetMapping("/health")
    public ResponseEntity<Map<String, String>> health() {
        return ResponseEntity.ok(Map.of("status", "UP", "service", "compliance"));
    }
}

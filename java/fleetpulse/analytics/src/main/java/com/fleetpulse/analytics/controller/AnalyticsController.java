package com.fleetpulse.analytics.controller;

import com.fleetpulse.analytics.service.AnalyticsService;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.Map;
import java.util.concurrent.ExecutionException;

/**
 * REST controller exposing analytics endpoints for report generation
 * and health checks.
 */
@RestController
@RequestMapping("/api/analytics")
public class AnalyticsController {

    @Autowired
    private AnalyticsService analyticsService;

    @GetMapping("/report/{reportId}")
    public ResponseEntity<Map<String, Object>> getReport(@PathVariable String reportId)
            throws ExecutionException, InterruptedException {
        Map<String, Object> report = analyticsService.generateAsyncReport(reportId).get();
        return ResponseEntity.ok(report);
    }

    @GetMapping("/health")
    public ResponseEntity<Map<String, String>> health() {
        return ResponseEntity.ok(Map.of("status", "UP", "service", "analytics"));
    }
}

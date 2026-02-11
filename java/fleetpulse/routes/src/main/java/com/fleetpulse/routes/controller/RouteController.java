package com.fleetpulse.routes.controller;

import com.fleetpulse.routes.service.RouteService;
import com.fleetpulse.routes.service.GeofenceService;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.math.BigDecimal;
import java.util.Map;

@RestController
@RequestMapping("/api/routes")
public class RouteController {

    @Autowired
    private RouteService routeService;

    @Autowired
    private GeofenceService geofenceService;

    @GetMapping("/cost")
    public ResponseEntity<Map<String, Object>> calculateCost(
            @RequestParam double distance, @RequestParam double rate) {
        double cost = routeService.calculateRouteCost(distance, rate);
        return ResponseEntity.ok(Map.of("cost", cost, "distance", distance, "rate", rate));
    }

    @GetMapping("/cost-per-mile")
    public ResponseEntity<Map<String, Object>> costPerMile(
            @RequestParam String totalCost, @RequestParam String totalMiles) {
        BigDecimal result = routeService.calculateCostPerMile(
            new BigDecimal(totalCost), new BigDecimal(totalMiles));
        return ResponseEntity.ok(Map.of("costPerMile", result));
    }

    @GetMapping("/geofence/check")
    public ResponseEntity<Map<String, Object>> checkGeofence(
            @RequestParam double lat, @RequestParam double lng,
            @RequestParam double centerLat, @RequestParam double centerLng,
            @RequestParam double radius) {
        boolean inside = geofenceService.isPointInCircle(lat, lng, centerLat, centerLng, radius);
        return ResponseEntity.ok(Map.of("inside", inside));
    }

    @GetMapping("/health")
    public ResponseEntity<Map<String, String>> health() {
        return ResponseEntity.ok(Map.of("status", "UP", "service", "routes"));
    }
}

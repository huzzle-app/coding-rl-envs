package com.vertexgrid.tracking.controller;

import com.vertexgrid.tracking.model.TrackingData;
import com.vertexgrid.tracking.service.TrackingService;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.Map;

@RestController
@RequestMapping("/api/tracking")
public class TrackingController {

    @Autowired
    private TrackingService trackingService;

    @PostMapping("/position")
    public ResponseEntity<Map<String, String>> recordPosition(@RequestBody TrackingData data) {
        trackingService.recordPosition(data);
        return ResponseEntity.ok(Map.of("status", "recorded"));
    }

    @GetMapping("/vehicle/{vehicleId}/latest")
    public ResponseEntity<TrackingData> getLatestPosition(@PathVariable String vehicleId) {
        TrackingData data = trackingService.getLatestPosition(vehicleId);
        if (data != null) {
            return ResponseEntity.ok(data);
        }
        return ResponseEntity.notFound().build();
    }

    @GetMapping("/vehicle/{vehicleId}/history")
    public ResponseEntity<List<TrackingData>> getHistory(@PathVariable String vehicleId) {
        return ResponseEntity.ok(trackingService.getHistory(vehicleId));
    }

    @GetMapping("/health")
    public ResponseEntity<Map<String, String>> health() {
        return ResponseEntity.ok(Map.of("status", "UP", "service", "tracking"));
    }
}

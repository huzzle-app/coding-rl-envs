package com.fleetpulse.vehicles.controller;

import com.fleetpulse.vehicles.model.Vehicle;
import com.fleetpulse.vehicles.service.VehicleService;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.Map;

@RestController
@RequestMapping("/api/vehicles")
public class VehicleController {

    @Autowired
    private VehicleService vehicleService;

    @GetMapping
    public ResponseEntity<List<Vehicle>> listVehicles(@RequestParam(required = false) String status) {
        if (status != null) {
            return ResponseEntity.ok(vehicleService.getActiveVehicles());
        }
        return ResponseEntity.ok(vehicleService.getActiveVehicles());
    }

    @GetMapping("/{id}")
    public ResponseEntity<Vehicle> getVehicle(@PathVariable Long id) {
        return ResponseEntity.ok(vehicleService.getVehicle(id));
    }

    @PostMapping
    public ResponseEntity<Vehicle> createVehicle(@RequestBody Vehicle vehicle) {
        return ResponseEntity.ok(vehicleService.createVehicle(vehicle));
    }

    @PutMapping("/{id}")
    public ResponseEntity<Vehicle> updateVehicle(@PathVariable Long id, @RequestBody Vehicle updates) {
        return ResponseEntity.ok(vehicleService.updateVehicle(id, updates));
    }

    @GetMapping("/search")
    public ResponseEntity<List<Vehicle>> search(@RequestParam String q) {
        return ResponseEntity.ok(vehicleService.searchVehicles(q));
    }

    @GetMapping("/health")
    public ResponseEntity<Map<String, String>> health() {
        return ResponseEntity.ok(Map.of("status", "UP", "service", "vehicles"));
    }
}

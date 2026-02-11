package com.fleetpulse.vehicles.consumer;

import com.fleetpulse.vehicles.service.VehicleService;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Component;

@Component
public class VehicleEventConsumer {

    private static final Logger log = LoggerFactory.getLogger(VehicleEventConsumer.class);

    @Autowired
    private VehicleService vehicleService;

    // Note: Kafka consumer configuration with auto-commit is in shared KafkaConfig (BUG L2)
    // This consumer would process vehicle status update events

    public void handleVehicleStatusUpdate(String vehicleId, String newStatus) {
        try {
            Long id = Long.parseLong(vehicleId);
            var vehicle = vehicleService.getVehicle(id);
            // Process status update
            log.info("Vehicle {} status updated to {}", vehicleId, newStatus);
        } catch (Exception e) {
            log.error("Failed to process vehicle event: {}", e.getMessage());
        }
    }
}

package com.fleetpulse.tracking;

import com.fleetpulse.tracking.model.TrackingEventBase;
import com.fleetpulse.tracking.model.TrackingEventBase.*;
import org.junit.jupiter.api.Tag;
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.*;

/**
 * Tests for TrackingEventBase sealed class hierarchy covering bug:
 *   K2 - Sealed class missing permit (ViolationEvent not in permits clause)
 *
 * When BUG K2 is present, ViolationEvent extends TrackingEventBase but is
 * NOT listed in the permits clause. This causes a compilation error.
 * After the fix, ViolationEvent should be permitted and fully functional.
 */
@Tag("unit")
public class TrackingEventTest {

    // =========================================================================
    
    // =========================================================================

    @Test
    void test_violationEvent_can_be_instantiated() {
        
        // After fix: ViolationEvent is permitted and can be created normally.
        ViolationEvent event = new ViolationEvent("v1", "SPEEDING");
        assertNotNull(event, "ViolationEvent should be creatable when permitted by sealed class");
    }

    @Test
    void test_violationEvent_has_vehicle_id() {
        ViolationEvent event = new ViolationEvent("vehicle-42", "HARD_BRAKE");
        assertEquals("vehicle-42", event.getVehicleId());
    }

    @Test
    void test_violationEvent_has_violation_type() {
        ViolationEvent event = new ViolationEvent("v1", "GEOFENCE_EXIT");
        assertEquals("GEOFENCE_EXIT", event.getViolationType());
    }

    @Test
    void test_violationEvent_has_timestamp() {
        long before = System.currentTimeMillis();
        ViolationEvent event = new ViolationEvent("v1", "SPEEDING");
        long after = System.currentTimeMillis();
        assertTrue(event.getTimestamp() >= before && event.getTimestamp() <= after,
            "Timestamp should be set to approximately current time");
    }

    @Test
    void test_violationEvent_is_instance_of_base() {
        
        ViolationEvent event = new ViolationEvent("v1", "IDLE_ENGINE");
        assertTrue(event instanceof TrackingEventBase,
            "ViolationEvent should be an instance of TrackingEventBase");
    }

    // =========================================================================
    // Other permitted subclasses (verify they still work correctly)
    // =========================================================================

    @Test
    void test_locationEvent_creation() {
        LocationEvent event = new LocationEvent("v1", 40.7128, -74.0060);
        assertEquals("v1", event.getVehicleId());
        assertEquals(40.7128, event.getLat(), 0.0001);
        assertEquals(-74.0060, event.getLng(), 0.0001);
    }

    @Test
    void test_speedEvent_creation() {
        SpeedEvent event = new SpeedEvent("v1", 88.5);
        assertEquals("v1", event.getVehicleId());
        assertEquals(88.5, event.getSpeed(), 0.001);
    }

    @Test
    void test_geofenceEvent_creation() {
        GeofenceEvent event = new GeofenceEvent("v1", "zone-A", true);
        assertEquals("v1", event.getVehicleId());
        assertEquals("zone-A", event.getGeofenceId());
        assertTrue(event.isEntered());
    }
}

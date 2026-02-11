package com.vertexgrid.vehicles;

import com.vertexgrid.vehicles.model.Vehicle;
import com.vertexgrid.vehicles.model.MaintenanceRecord;
import org.junit.jupiter.api.Tag;
import org.junit.jupiter.api.Test;

import java.time.LocalDateTime;
import java.util.HashMap;
import java.util.HashSet;
import java.util.Map;
import java.util.Set;

import static org.junit.jupiter.api.Assertions.*;

/**
 * Tests for Vehicle model entity focusing on:
 *   B1 - Mutable HashMap key: equals/hashCode uses mutable licensePlate field.
 *         After mutation, HashMap and HashSet lookups fail.
 *         Fix: Use only id (immutable after persist) for equals/hashCode.
 */
@Tag("unit")
public class VehicleModelTest {

    // --- BUG B1: Mutable HashMap key ---

    @Test
    void test_equals_usesLicensePlate_buggy() {
        
        Vehicle v1 = new Vehicle();
        v1.setLicensePlate("ABC-1234");
        v1.setVin("VIN0001");

        Vehicle v2 = new Vehicle();
        v2.setLicensePlate("ABC-1234");
        v2.setVin("VIN0002");

        // Two different vehicles with same plate considered equal (problematic)
        // Fixed version should use id-based equality
        assertEquals(v1, v2, "Buggy: equals uses licensePlate, so same plate = equal");
    }

    @Test
    void test_hashMap_lookup_fails_after_licensePlate_mutation() {
        
        // mutating licensePlate breaks the hash bucket lookup
        Vehicle vehicle = new Vehicle();
        vehicle.setLicensePlate("ORIG-001");
        vehicle.setVin("HASHVEHICLE01");

        Map<Vehicle, String> map = new HashMap<>();
        map.put(vehicle, "assigned-route-1");

        // Lookup works before mutation
        assertEquals("assigned-route-1", map.get(vehicle));

        // Mutate the licensePlate (which is used in hashCode)
        vehicle.setLicensePlate("CHANGED-001");

        
        // Fixed version using id-based hashCode would still find it
        String retrieved = map.get(vehicle);
        assertNotNull(retrieved,
            "HashMap lookup should succeed after mutation if equals/hashCode uses immutable id");
        assertEquals("assigned-route-1", retrieved);
    }

    @Test
    void test_hashSet_contains_fails_after_mutation() {
        
        Vehicle vehicle = new Vehicle();
        vehicle.setLicensePlate("SET-001");
        vehicle.setVin("SETVEHICLE01");

        Set<Vehicle> set = new HashSet<>();
        set.add(vehicle);

        assertTrue(set.contains(vehicle), "Should contain vehicle before mutation");

        // Mutate the key field
        vehicle.setLicensePlate("SET-CHANGED");

        
        assertTrue(set.contains(vehicle),
            "HashSet should still contain vehicle after licensePlate mutation (fix: use id)");
    }

    @Test
    void test_hashMap_remove_fails_after_mutation() {
        
        Vehicle vehicle = new Vehicle();
        vehicle.setLicensePlate("REM-001");

        Map<Vehicle, String> map = new HashMap<>();
        map.put(vehicle, "value");
        assertEquals(1, map.size());

        vehicle.setLicensePlate("REM-CHANGED");

        
        map.remove(vehicle);
        assertEquals(0, map.size(),
            "Should be able to remove vehicle from map even after licensePlate change (fix: id-based hashCode)");
    }

    @Test
    void test_equals_shouldUseId_notLicensePlate() {
        // Fixed version: two vehicles with same id are equal regardless of licensePlate
        Vehicle v1 = new Vehicle();
        v1.setId(1L);
        v1.setLicensePlate("AAA-111");

        Vehicle v2 = new Vehicle();
        v2.setId(1L);
        v2.setLicensePlate("BBB-222");

        // After fix, same id means equal (BaseEntity.equals uses id)
        assertEquals(v1, v2,
            "Vehicles with same id should be equal regardless of licensePlate");
    }

    @Test
    void test_hashCode_consistent_after_mutation() {
        // Fixed version: hashCode should not change when mutable fields change
        Vehicle vehicle = new Vehicle();
        vehicle.setId(42L);
        vehicle.setLicensePlate("CONS-001");

        int hash1 = vehicle.hashCode();
        vehicle.setLicensePlate("CONS-CHANGED");
        int hash2 = vehicle.hashCode();

        assertEquals(hash1, hash2,
            "hashCode should remain stable after mutable field changes (fix: use id-based)");
    }

    // --- JPA relationship tests ---

    @Test
    void test_vehicle_defaultValues() {
        Vehicle vehicle = new Vehicle();
        assertEquals("IDLE", vehicle.getStatus());
        assertEquals(100.0, vehicle.getFuelLevel());
        assertEquals(0.0, vehicle.getMileage());
        assertNotNull(vehicle.getMaintenanceRecords());
        assertTrue(vehicle.getMaintenanceRecords().isEmpty());
    }

    @Test
    void test_vehicle_maintenanceRecordsBidirectional() {
        Vehicle vehicle = new Vehicle();
        vehicle.setVin("BIDIR001");
        vehicle.setLicensePlate("BI-001");

        MaintenanceRecord record = new MaintenanceRecord();
        record.setMaintenanceType("TIRE_ROTATION");
        record.setCost(150.0);
        record.setPerformedAt(LocalDateTime.now());
        record.setVehicle(vehicle);

        vehicle.getMaintenanceRecords().add(record);

        assertEquals(1, vehicle.getMaintenanceRecords().size());
        assertSame(vehicle, record.getVehicle());
        assertEquals("TIRE_ROTATION", vehicle.getMaintenanceRecords().get(0).getMaintenanceType());
    }

    @Test
    void test_vehicle_allFields() {
        Vehicle vehicle = new Vehicle();
        vehicle.setVin("12345678901234567");
        vehicle.setLicensePlate("FL-PLATE");
        vehicle.setMake("Tesla");
        vehicle.setModel("Model 3");
        vehicle.setYear(2024);
        vehicle.setStatus("ACTIVE");
        vehicle.setDriverId(100L);
        vehicle.setCurrentLat(37.7749);
        vehicle.setCurrentLng(-122.4194);
        vehicle.setFuelLevel(80.0);
        vehicle.setMileage(15000.0);
        vehicle.setLastMaintenance(LocalDateTime.of(2024, 6, 15, 10, 0));

        assertEquals("12345678901234567", vehicle.getVin());
        assertEquals("FL-PLATE", vehicle.getLicensePlate());
        assertEquals("Tesla", vehicle.getMake());
        assertEquals("Model 3", vehicle.getModel());
        assertEquals(2024, vehicle.getYear());
        assertEquals("ACTIVE", vehicle.getStatus());
        assertEquals(100L, vehicle.getDriverId());
        assertEquals(37.7749, vehicle.getCurrentLat());
        assertEquals(-122.4194, vehicle.getCurrentLng());
        assertEquals(80.0, vehicle.getFuelLevel());
        assertEquals(15000.0, vehicle.getMileage());
        assertNotNull(vehicle.getLastMaintenance());
    }

    @Test
    void test_vehicle_recentEventsInitialized() {
        Vehicle vehicle = new Vehicle();
        assertNotNull(vehicle.getRecentEvents());
        assertTrue(vehicle.getRecentEvents().isEmpty());
    }
}

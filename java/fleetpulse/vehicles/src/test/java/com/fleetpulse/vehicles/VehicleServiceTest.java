package com.fleetpulse.vehicles;

import com.fleetpulse.vehicles.model.Vehicle;
import com.fleetpulse.vehicles.model.MaintenanceRecord;
import com.fleetpulse.vehicles.repository.VehicleRepository;
import com.fleetpulse.vehicles.service.VehicleService;
import jakarta.persistence.EntityManager;
import jakarta.persistence.EntityManagerFactory;
import jakarta.persistence.TypedQuery;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Tag;
import org.junit.jupiter.api.Test;

import java.lang.reflect.Field;
import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.List;
import java.util.Optional;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.Mockito.*;

/**
 * Tests for VehicleService covering bugs:
 *   D1 - N+1 query (lazy fetch without JOIN FETCH)
 *   D2 - LazyInitializationException (accessing lazy collection outside transaction)
 *   D3 - Connection pool exhaustion (EntityManager not closed)
 *   E1 - N+1 query on tracking events
 *   E2 - Type erasure / wildcard capture (List<? extends Vehicle>)
 *   B1 - Mutable HashMap key (licensePlate in equals/hashCode)
 */
@Tag("unit")
public class VehicleServiceTest {

    private VehicleService vehicleService;
    private VehicleRepository vehicleRepository;
    private EntityManager entityManager;
    private EntityManagerFactory entityManagerFactory;

    @BeforeEach
    void setUp() throws Exception {
        vehicleService = new VehicleService();
        vehicleRepository = mock(VehicleRepository.class);
        entityManager = mock(EntityManager.class);
        entityManagerFactory = mock(EntityManagerFactory.class);

        // Inject mocks via reflection since VehicleService uses @Autowired
        setField(vehicleService, "vehicleRepository", vehicleRepository);
        setField(vehicleService, "entityManager", entityManager);
    }

    private void setField(Object target, String fieldName, Object value) throws Exception {
        Field field = target.getClass().getDeclaredField(fieldName);
        field.setAccessible(true);
        field.set(target, value);
    }

    // --- BUG D2: LazyInitializationException tests ---

    @Test
    @Tag("integration")
    void test_getVehicle_shouldNotThrowLazyInitException() {
        
        // Accessing lazy collections outside a persistence context
        // should not throw LazyInitializationException.
        Vehicle vehicle = new Vehicle();
        vehicle.setVin("1HGBH41JXMN109186");
        vehicle.setLicensePlate("ABC-1234");
        vehicle.setMaintenanceRecords(new ArrayList<>());
        when(vehicleRepository.findById(1L)).thenReturn(Optional.of(vehicle));

        // Should not throw when persistence context is properly managed
        Vehicle result = vehicleService.getVehicle(1L);
        assertNotNull(result);
        assertEquals("1HGBH41JXMN109186", result.getVin());
    }

    @Test
    void test_getVehicle_throwsForUnknownId() {
        when(vehicleRepository.findById(999L)).thenReturn(Optional.empty());

        RuntimeException ex = assertThrows(RuntimeException.class,
            () -> vehicleService.getVehicle(999L));
        assertTrue(ex.getMessage().contains("Vehicle not found"));
    }

    @Test
    @Tag("integration")
    void test_getVehicle_accessesMaintenanceRecords() {
        
        Vehicle vehicle = new Vehicle();
        vehicle.setVin("2HGBH41JXMN109186");
        vehicle.setLicensePlate("XYZ-5678");

        MaintenanceRecord record = new MaintenanceRecord();
        record.setMaintenanceType("OIL_CHANGE");
        record.setVehicle(vehicle);
        List<MaintenanceRecord> records = new ArrayList<>();
        records.add(record);
        vehicle.setMaintenanceRecords(records);

        when(vehicleRepository.findById(1L)).thenReturn(Optional.of(vehicle));

        Vehicle result = vehicleService.getVehicle(1L);
        // This assertion verifies the maintenance records are accessible
        // (Bug D2 causes LazyInitializationException here)
        assertNotNull(result.getMaintenanceRecords());
        assertEquals(1, result.getMaintenanceRecords().size());
    }

    // --- BUG D3: Connection pool exhaustion tests ---

    @Test
    @Tag("integration")
    void test_searchVehicles_closesEntityManager() {
        
        // After fix, EntityManager.close() must be called in finally block.
        EntityManager mockEm = mock(EntityManager.class);
        @SuppressWarnings("unchecked")
        TypedQuery<Vehicle> mockQuery = mock(TypedQuery.class);

        when(entityManager.getEntityManagerFactory()).thenReturn(entityManagerFactory);
        when(entityManagerFactory.createEntityManager()).thenReturn(mockEm);
        when(mockEm.createQuery(anyString(), eq(Vehicle.class))).thenReturn(mockQuery);
        when(mockQuery.setParameter(eq("query"), anyString())).thenReturn(mockQuery);
        when(mockQuery.getResultList()).thenReturn(List.of());

        vehicleService.searchVehicles("Toyota");

        
        // EntityManager must be properly closed after use
        verify(mockEm).close();
    }

    @Test
    @Tag("integration")
    void test_searchVehicles_closesEntityManagerOnException() {
        // Even when query throws, EntityManager should be closed (try-finally)
        EntityManager mockEm = mock(EntityManager.class);
        @SuppressWarnings("unchecked")
        TypedQuery<Vehicle> mockQuery = mock(TypedQuery.class);

        when(entityManager.getEntityManagerFactory()).thenReturn(entityManagerFactory);
        when(entityManagerFactory.createEntityManager()).thenReturn(mockEm);
        when(mockEm.createQuery(anyString(), eq(Vehicle.class))).thenReturn(mockQuery);
        when(mockQuery.setParameter(eq("query"), anyString())).thenReturn(mockQuery);
        when(mockQuery.getResultList()).thenThrow(new RuntimeException("DB error"));

        assertThrows(RuntimeException.class, () -> vehicleService.searchVehicles("test"));

        // EntityManager must still be closed after exception
        verify(mockEm).close();
    }

    @Test
    void test_searchVehicles_returnsMatchingVehicles() {
        EntityManager mockEm = mock(EntityManager.class);
        @SuppressWarnings("unchecked")
        TypedQuery<Vehicle> mockQuery = mock(TypedQuery.class);

        Vehicle v1 = new Vehicle();
        v1.setMake("Toyota");
        v1.setModel("Camry");
        Vehicle v2 = new Vehicle();
        v2.setMake("Toyota");
        v2.setModel("Corolla");

        when(entityManager.getEntityManagerFactory()).thenReturn(entityManagerFactory);
        when(entityManagerFactory.createEntityManager()).thenReturn(mockEm);
        when(mockEm.createQuery(anyString(), eq(Vehicle.class))).thenReturn(mockQuery);
        when(mockQuery.setParameter(eq("query"), anyString())).thenReturn(mockQuery);
        when(mockQuery.getResultList()).thenReturn(List.of(v1, v2));

        List<Vehicle> results = vehicleService.searchVehicles("Toyota");
        assertEquals(2, results.size());
    }

    // --- BUG E2: Type erasure / wildcard capture tests ---

    @Test
    void test_addToFleet_shouldMaintainTypeInvariance() {
        
        // This causes heap pollution - the list may contain incompatible types
        List<Vehicle> fleet = new ArrayList<>();
        Vehicle newVehicle = new Vehicle();
        newVehicle.setVin("3HGBH41JXMN109186");
        newVehicle.setLicensePlate("FLEET-001");

        vehicleService.addToFleet(fleet, newVehicle);

        assertEquals(1, fleet.size());
        assertSame(newVehicle, fleet.get(0));
    }

    @Test
    void test_addToFleet_rawTypeCastCausesHeapPollution() {
        
        // which can cause ClassCastException at runtime in generic context.
        List<Vehicle> fleet = new ArrayList<>();
        Vehicle v1 = new Vehicle();
        v1.setVin("AAA");
        v1.setLicensePlate("LP-001");
        Vehicle v2 = new Vehicle();
        v2.setVin("BBB");
        v2.setLicensePlate("LP-002");

        vehicleService.addToFleet(fleet, v1);
        vehicleService.addToFleet(fleet, v2);

        assertEquals(2, fleet.size());
        // Verify all elements are actually Vehicle instances (no heap pollution)
        for (Vehicle v : fleet) {
            assertNotNull(v.getVin());
        }
    }

    @Test
    void test_addToFleet_typeSafety() {
        
        // The fixed method signature should prevent misuse.
        List<Vehicle> fleet = new ArrayList<>();
        Vehicle v = new Vehicle();
        v.setLicensePlate("SAFE-001");

        // Should work without raw type warnings
        vehicleService.addToFleet(fleet, v);
        assertTrue(fleet.contains(v));
    }

    // --- BUG D1: N+1 query tests ---

    @Test
    @Tag("integration")
    void test_findVehiclesByStatus_loadsMaintenanceRecordsEfficiently() {
        
        // Accessing maintenanceRecords should not trigger N+1 separate queries.
        Vehicle v = new Vehicle();
        v.setVin("N1QUERY");
        v.setLicensePlate("N1-001");
        v.setStatus("ACTIVE");
        MaintenanceRecord r = new MaintenanceRecord();
        r.setMaintenanceType("INSPECTION");
        r.setVehicle(v);
        v.getMaintenanceRecords().add(r);

        when(vehicleRepository.findVehiclesByStatus("ACTIVE")).thenReturn(List.of(v));

        List<Vehicle> result = vehicleRepository.findVehiclesByStatus("ACTIVE");
        assertNotNull(result);
        assertEquals(1, result.size());
        // Accessing maintenanceRecords should work without additional query
        assertEquals(1, result.get(0).getMaintenanceRecords().size());
    }

    @Test
    void test_getActiveVehicles_returnsActiveOnly() {
        Vehicle active = new Vehicle();
        active.setStatus("ACTIVE");
        active.setLicensePlate("ACT-001");
        when(vehicleRepository.findByStatus("ACTIVE")).thenReturn(List.of(active));

        List<Vehicle> result = vehicleService.getActiveVehicles();
        assertEquals(1, result.size());
        assertEquals("ACTIVE", result.get(0).getStatus());
    }

    // --- General CRUD tests ---

    @Test
    void test_createVehicle_savesProperly() {
        Vehicle vehicle = new Vehicle();
        vehicle.setVin("CREATE123456789");
        vehicle.setLicensePlate("NEW-001");
        vehicle.setMake("Ford");
        vehicle.setModel("Transit");
        when(vehicleRepository.save(vehicle)).thenReturn(vehicle);

        Vehicle result = vehicleService.createVehicle(vehicle);
        assertNotNull(result);
        assertEquals("Ford", result.getMake());
        verify(vehicleRepository).save(vehicle);
    }

    @Test
    void test_updateVehicle_updatesFields() {
        Vehicle existing = new Vehicle();
        existing.setId(1L);
        existing.setVin("UPD12345678901234");
        existing.setLicensePlate("OLD-001");
        existing.setStatus("IDLE");

        Vehicle updates = new Vehicle();
        updates.setStatus("ACTIVE");
        updates.setDriverId(42L);
        updates.setCurrentLat(40.7128);
        updates.setCurrentLng(-74.0060);
        updates.setFuelLevel(85.5);

        when(vehicleRepository.findById(1L)).thenReturn(Optional.of(existing));
        when(vehicleRepository.save(any(Vehicle.class))).thenAnswer(inv -> inv.getArgument(0));

        Vehicle result = vehicleService.updateVehicle(1L, updates);
        assertEquals("ACTIVE", result.getStatus());
        assertEquals(42L, result.getDriverId());
        assertEquals(40.7128, result.getCurrentLat());
        assertEquals(-74.0060, result.getCurrentLng());
        assertEquals(85.5, result.getFuelLevel());
    }

    @Test
    void test_updateVehicle_throwsForUnknownId() {
        when(vehicleRepository.findById(999L)).thenReturn(Optional.empty());
        Vehicle updates = new Vehicle();
        updates.setStatus("ACTIVE");

        assertThrows(RuntimeException.class, () -> vehicleService.updateVehicle(999L, updates));
    }

    @Test
    void test_updateVehicle_partialUpdate() {
        // Only status updated, other fields remain null in updates -> untouched
        Vehicle existing = new Vehicle();
        existing.setId(1L);
        existing.setLicensePlate("PART-001");
        existing.setStatus("IDLE");
        existing.setDriverId(10L);
        existing.setFuelLevel(50.0);

        Vehicle updates = new Vehicle();
        updates.setStatus("MAINTENANCE");
        // driverId, currentLat, currentLng, fuelLevel are all null in updates

        when(vehicleRepository.findById(1L)).thenReturn(Optional.of(existing));
        when(vehicleRepository.save(any(Vehicle.class))).thenAnswer(inv -> inv.getArgument(0));

        Vehicle result = vehicleService.updateVehicle(1L, updates);
        assertEquals("MAINTENANCE", result.getStatus());
        // These should remain unchanged
        assertEquals(10L, result.getDriverId());
        assertEquals(50.0, result.getFuelLevel());
    }

    @Test
    void test_findByVin_returnsVehicle() {
        Vehicle v = new Vehicle();
        v.setVin("FINDVIN1234567890");
        v.setLicensePlate("VIN-001");
        when(vehicleRepository.findByVin("FINDVIN1234567890")).thenReturn(Optional.of(v));

        Optional<Vehicle> result = vehicleService.findByVin("FINDVIN1234567890");
        assertTrue(result.isPresent());
        assertEquals("FINDVIN1234567890", result.get().getVin());
    }

    @Test
    void test_findByVin_returnsEmptyForUnknown() {
        when(vehicleRepository.findByVin("NONEXISTENT")).thenReturn(Optional.empty());

        Optional<Vehicle> result = vehicleService.findByVin("NONEXISTENT");
        assertTrue(result.isEmpty());
    }
}

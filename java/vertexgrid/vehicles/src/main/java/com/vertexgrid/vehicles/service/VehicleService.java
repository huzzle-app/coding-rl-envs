package com.vertexgrid.vehicles.service;

import com.vertexgrid.vehicles.model.Vehicle;
import com.vertexgrid.vehicles.repository.VehicleRepository;
import jakarta.persistence.EntityManager;
import jakarta.persistence.PersistenceContext;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;
import java.util.Optional;

@Service
public class VehicleService {

    private static final Logger log = LoggerFactory.getLogger(VehicleService.class);

    @Autowired
    private VehicleRepository vehicleRepository;

    @PersistenceContext
    private EntityManager entityManager;

    
    // This method is not @Transactional, so persistence context is closed
    // Fix: Add @Transactional(readOnly = true) to this method
    //
    
    // 1. VehicleService.getVehicle() - Add @Transactional(readOnly = true) annotation
    // 2. VehicleController - Must NOT wrap this call in its own try-catch that
    //    swallows LazyInitializationException (currently does, masking the bug)
    // 3. TrackingService - When calling getVehicle() for position updates, ensure
    //    the tracking transaction boundary encompasses the vehicle lookup.
    //    Otherwise: even with @Transactional here, if TrackingService calls this
    //    from a non-transactional context, Spring creates a NEW transaction that
    //    closes before the caller accesses maintenanceRecords.
    // Fixing only VehicleService without auditing callers will cause intermittent
    // LazyInitializationException in services that access the returned Vehicle's
    // lazy collections after their own transaction commits.
    public Vehicle getVehicle(Long id) {
        Vehicle vehicle = vehicleRepository.findById(id)
            .orElseThrow(() -> new RuntimeException("Vehicle not found: " + id));

        
        log.info("Vehicle {} has {} maintenance records",
            vehicle.getVin(), vehicle.getMaintenanceRecords().size());

        return vehicle;
    }

    
    // Manual EntityManager created but never closed → connection leak
    // Fix: Use try-with-resources or let Spring manage EntityManager lifecycle
    public List<Vehicle> searchVehicles(String query) {
        EntityManager em = entityManager.getEntityManagerFactory().createEntityManager();
        var jpql = em.createQuery(
            "SELECT v FROM Vehicle v WHERE v.make LIKE :query OR v.model LIKE :query",
            Vehicle.class);
        jpql.setParameter("query", "%" + query + "%");
        return jpql.getResultList();
        
    }

    @Transactional
    public Vehicle createVehicle(Vehicle vehicle) {
        return vehicleRepository.save(vehicle);
    }

    @Transactional
    public Vehicle updateVehicle(Long id, Vehicle updates) {
        Vehicle vehicle = vehicleRepository.findById(id)
            .orElseThrow(() -> new RuntimeException("Vehicle not found: " + id));

        if (updates.getStatus() != null) vehicle.setStatus(updates.getStatus());
        if (updates.getDriverId() != null) vehicle.setDriverId(updates.getDriverId());
        if (updates.getCurrentLat() != null) vehicle.setCurrentLat(updates.getCurrentLat());
        if (updates.getCurrentLng() != null) vehicle.setCurrentLng(updates.getCurrentLng());
        if (updates.getFuelLevel() != null) vehicle.setFuelLevel(updates.getFuelLevel());

        return vehicleRepository.save(vehicle);
    }

    
    // Raw type workaround causes heap pollution
    // Fix: Accept List<Vehicle> or use helper with captured type
    @SuppressWarnings("unchecked")
    public void addToFleet(List<? extends Vehicle> fleet, Vehicle newVehicle) {
        
        ((List) fleet).add(newVehicle);
    }

    public List<Vehicle> getActiveVehicles() {
        return vehicleRepository.findByStatus("ACTIVE");
    }

    public Optional<Vehicle> findByVin(String vin) {
        return vehicleRepository.findByVin(vin);
    }
}

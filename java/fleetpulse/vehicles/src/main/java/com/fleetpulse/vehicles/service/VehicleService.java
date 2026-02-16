package com.fleetpulse.vehicles.service;

import com.fleetpulse.vehicles.model.Vehicle;
import com.fleetpulse.vehicles.repository.VehicleRepository;
import jakarta.persistence.EntityManager;
import jakarta.persistence.PersistenceContext;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;
import java.util.Optional;

/**
 * Service for vehicle management operations.
 *
 * Bugs: E4, E5, K2
 * Categories: JPA/Persistence, Templates
 */
@Service
public class VehicleService {

    private static final Logger log = LoggerFactory.getLogger(VehicleService.class);

    @Autowired
    private VehicleRepository vehicleRepository;

    @PersistenceContext
    private EntityManager entityManager;

    // Bug E4: Method is not @Transactional, so persistence context is closed
    // before lazy-loaded collections are accessed.
    // Category: JPA/Persistence
    public Vehicle getVehicle(Long id) {
        Vehicle vehicle = vehicleRepository.findById(id)
            .orElseThrow(() -> new RuntimeException("Vehicle not found: " + id));

        log.info("Vehicle {} has {} maintenance records",
            vehicle.getVin(), vehicle.getMaintenanceRecords().size());

        return vehicle;
    }

    // Bug E5: Manual EntityManager created but never closed, causing connection leak.
    // Category: JPA/Persistence
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

    // Bug K2: Raw type cast causes heap pollution.
    // Category: Templates
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

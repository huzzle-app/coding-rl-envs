package com.fleetpulse.vehicles.repository;

import com.fleetpulse.vehicles.model.Vehicle;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.stereotype.Repository;

import java.util.List;
import java.util.Optional;

/**
 * Repository for Vehicle entity persistence operations.
 *
 * Bugs: E3
 * Categories: JPA/Persistence
 */
@Repository
public interface VehicleRepository extends JpaRepository<Vehicle, Long> {

    Optional<Vehicle> findByVin(String vin);

    List<Vehicle> findByStatus(String status);

    List<Vehicle> findByDriverId(Long driverId);

    // Bug E3: Loading vehicles and accessing records causes N+1 queries.
    // Category: JPA/Persistence
    @Query("SELECT v FROM Vehicle v WHERE v.status = :status")
    List<Vehicle> findVehiclesByStatus(@Param("status") String status);
}

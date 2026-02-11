package com.vertexgrid.vehicles.repository;

import com.vertexgrid.vehicles.model.Vehicle;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.stereotype.Repository;

import java.util.List;
import java.util.Optional;

@Repository
public interface VehicleRepository extends JpaRepository<Vehicle, Long> {

    Optional<Vehicle> findByVin(String vin);

    List<Vehicle> findByStatus(String status);

    List<Vehicle> findByDriverId(Long driverId);

    
    // Loading vehicles and accessing records causes N+1 queries
    @Query("SELECT v FROM Vehicle v WHERE v.status = :status")
    List<Vehicle> findVehiclesByStatus(@Param("status") String status);

    // Proper fix would be:
    // @Query("SELECT v FROM Vehicle v JOIN FETCH v.maintenanceRecords WHERE v.status = :status")
}

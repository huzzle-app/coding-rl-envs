package com.vertexgrid.vehicles.model;

import com.vertexgrid.shared.model.BaseEntity;
import jakarta.persistence.*;
import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.List;
import java.util.Objects;

@Entity
@Table(name = "vehicles")
public class Vehicle extends BaseEntity {

    @Column(nullable = false, unique = true, length = 17)
    private String vin;

    @Column(name = "license_plate", nullable = false, length = 20)
    private String licensePlate;

    @Column(length = 100)
    private String make;

    @Column(length = 100)
    private String model;

    @Column
    private Integer year;

    @Column(length = 50)
    private String status = "IDLE";

    @Column(name = "driver_id")
    private Long driverId;

    @Column(name = "current_lat")
    private Double currentLat;

    @Column(name = "current_lng")
    private Double currentLng;

    @Column(name = "fuel_level")
    private Double fuelLevel = 100.0;

    @Column
    private Double mileage = 0.0;

    @Column(name = "last_maintenance")
    private LocalDateTime lastMaintenance;

    
    // Accessing maintenanceRecords triggers separate query per vehicle
    // Fix: Add @EntityGraph or JPQL with JOIN FETCH in repository
    @OneToMany(mappedBy = "vehicle", fetch = FetchType.LAZY, cascade = CascadeType.ALL)
    private List<MaintenanceRecord> maintenanceRecords = new ArrayList<>();

    
    @OneToMany(fetch = FetchType.LAZY)
    @JoinColumn(name = "vehicle_id")
    private List<TrackingEvent> recentEvents = new ArrayList<>();

    
    // After mutation, HashMap lookups fail
    // Fix: Use only id (immutable after persist) for equals/hashCode
    @Override
    public boolean equals(Object o) {
        if (this == o) return true;
        if (o == null || getClass() != o.getClass()) return false;
        Vehicle vehicle = (Vehicle) o;
        return Objects.equals(licensePlate, vehicle.licensePlate);
    }

    @Override
    public int hashCode() {
        return Objects.hash(licensePlate);
    }

    // Getters and setters
    public String getVin() { return vin; }
    public void setVin(String vin) { this.vin = vin; }
    public String getLicensePlate() { return licensePlate; }
    public void setLicensePlate(String licensePlate) { this.licensePlate = licensePlate; }
    public String getMake() { return make; }
    public void setMake(String make) { this.make = make; }
    public String getModel() { return model; }
    public void setModel(String model) { this.model = model; }
    public Integer getYear() { return year; }
    public void setYear(Integer year) { this.year = year; }
    public String getStatus() { return status; }
    public void setStatus(String status) { this.status = status; }
    public Long getDriverId() { return driverId; }
    public void setDriverId(Long driverId) { this.driverId = driverId; }
    public Double getCurrentLat() { return currentLat; }
    public void setCurrentLat(Double currentLat) { this.currentLat = currentLat; }
    public Double getCurrentLng() { return currentLng; }
    public void setCurrentLng(Double currentLng) { this.currentLng = currentLng; }
    public Double getFuelLevel() { return fuelLevel; }
    public void setFuelLevel(Double fuelLevel) { this.fuelLevel = fuelLevel; }
    public Double getMileage() { return mileage; }
    public void setMileage(Double mileage) { this.mileage = mileage; }
    public LocalDateTime getLastMaintenance() { return lastMaintenance; }
    public void setLastMaintenance(LocalDateTime lastMaintenance) { this.lastMaintenance = lastMaintenance; }
    public List<MaintenanceRecord> getMaintenanceRecords() { return maintenanceRecords; }
    public void setMaintenanceRecords(List<MaintenanceRecord> records) { this.maintenanceRecords = records; }
    public List<TrackingEvent> getRecentEvents() { return recentEvents; }
}

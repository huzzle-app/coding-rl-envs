package com.fleetpulse.vehicles.model;

import com.fleetpulse.shared.model.BaseEntity;
import jakarta.persistence.*;
import java.time.LocalDateTime;

@Entity
@Table(name = "maintenance_records")
public class MaintenanceRecord extends BaseEntity {

    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "vehicle_id")
    private Vehicle vehicle;

    @Column(name = "maintenance_type", length = 100)
    private String maintenanceType;

    @Column
    private String description;

    @Column(name = "performed_at")
    private LocalDateTime performedAt;

    @Column
    private Double cost;

    public Vehicle getVehicle() { return vehicle; }
    public void setVehicle(Vehicle vehicle) { this.vehicle = vehicle; }
    public String getMaintenanceType() { return maintenanceType; }
    public void setMaintenanceType(String type) { this.maintenanceType = type; }
    public String getDescription() { return description; }
    public void setDescription(String desc) { this.description = desc; }
    public LocalDateTime getPerformedAt() { return performedAt; }
    public void setPerformedAt(LocalDateTime at) { this.performedAt = at; }
    public Double getCost() { return cost; }
    public void setCost(Double cost) { this.cost = cost; }
}

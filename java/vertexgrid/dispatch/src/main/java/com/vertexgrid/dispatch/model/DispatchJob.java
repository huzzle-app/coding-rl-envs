package com.vertexgrid.dispatch.model;

import com.vertexgrid.shared.model.BaseEntity;
import jakarta.persistence.*;
import java.time.LocalDateTime;

@Entity
@Table(name = "dispatch_jobs")
public class DispatchJob extends BaseEntity {

    @Column(nullable = false, length = 255)
    private String title;

    @Column(columnDefinition = "TEXT")
    private String description;

    @Column(length = 50)
    private String priority = "NORMAL";

    @Column(length = 50)
    private String status = "PENDING";

    @Column(name = "vehicle_id")
    private Long vehicleId;

    @Column(name = "driver_id")
    private Long driverId;

    @Column(name = "route_id")
    private Long routeId;

    @Column(name = "pickup_lat")
    private Double pickupLat;

    @Column(name = "pickup_lng")
    private Double pickupLng;

    @Column(name = "delivery_lat")
    private Double deliveryLat;

    @Column(name = "delivery_lng")
    private Double deliveryLng;

    @Column(name = "scheduled_start")
    private LocalDateTime scheduledStart;

    @Column(name = "scheduled_end")
    private LocalDateTime scheduledEnd;

    @Column(name = "actual_start")
    private LocalDateTime actualStart;

    @Column(name = "actual_end")
    private LocalDateTime actualEnd;

    // Getters and setters
    public String getTitle() { return title; }
    public void setTitle(String title) { this.title = title; }
    public String getDescription() { return description; }
    public void setDescription(String desc) { this.description = desc; }
    public String getPriority() { return priority; }
    public void setPriority(String priority) { this.priority = priority; }
    public String getStatus() { return status; }
    public void setStatus(String status) { this.status = status; }
    public Long getVehicleId() { return vehicleId; }
    public void setVehicleId(Long id) { this.vehicleId = id; }
    public Long getDriverId() { return driverId; }
    public void setDriverId(Long id) { this.driverId = id; }
    public Long getRouteId() { return routeId; }
    public void setRouteId(Long id) { this.routeId = id; }
    public Double getPickupLat() { return pickupLat; }
    public void setPickupLat(Double lat) { this.pickupLat = lat; }
    public Double getPickupLng() { return pickupLng; }
    public void setPickupLng(Double lng) { this.pickupLng = lng; }
    public Double getDeliveryLat() { return deliveryLat; }
    public void setDeliveryLat(Double lat) { this.deliveryLat = lat; }
    public Double getDeliveryLng() { return deliveryLng; }
    public void setDeliveryLng(Double lng) { this.deliveryLng = lng; }
    public LocalDateTime getScheduledStart() { return scheduledStart; }
    public void setScheduledStart(LocalDateTime t) { this.scheduledStart = t; }
    public LocalDateTime getScheduledEnd() { return scheduledEnd; }
    public void setScheduledEnd(LocalDateTime t) { this.scheduledEnd = t; }
    public LocalDateTime getActualStart() { return actualStart; }
    public void setActualStart(LocalDateTime t) { this.actualStart = t; }
    public LocalDateTime getActualEnd() { return actualEnd; }
    public void setActualEnd(LocalDateTime t) { this.actualEnd = t; }
}

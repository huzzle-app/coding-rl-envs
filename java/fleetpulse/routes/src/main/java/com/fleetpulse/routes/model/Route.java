package com.fleetpulse.routes.model;

import com.fleetpulse.shared.model.BaseEntity;
import jakarta.persistence.*;
import java.util.ArrayList;
import java.util.List;

@Entity
@Table(name = "routes")
public class Route extends BaseEntity {

    @Column(length = 255)
    private String name;

    @Column(name = "origin_lat", nullable = false)
    private Double originLat;

    @Column(name = "origin_lng", nullable = false)
    private Double originLng;

    @Column(name = "destination_lat", nullable = false)
    private Double destinationLat;

    @Column(name = "destination_lng", nullable = false)
    private Double destinationLng;

    @Column(name = "distance_km")
    private Double distanceKm;

    @Column(name = "estimated_duration_minutes")
    private Integer estimatedDurationMinutes;

    @Column(length = 50)
    private String status = "PLANNED";

    @Column(name = "vehicle_id")
    private Long vehicleId;

    @OneToMany(mappedBy = "route", cascade = CascadeType.ALL, fetch = FetchType.LAZY)
    @OrderBy("sequenceNumber ASC")
    private List<RouteWaypoint> waypoints = new ArrayList<>();

    // Getters and setters
    public String getName() { return name; }
    public void setName(String name) { this.name = name; }
    public Double getOriginLat() { return originLat; }
    public void setOriginLat(Double lat) { this.originLat = lat; }
    public Double getOriginLng() { return originLng; }
    public void setOriginLng(Double lng) { this.originLng = lng; }
    public Double getDestinationLat() { return destinationLat; }
    public void setDestinationLat(Double lat) { this.destinationLat = lat; }
    public Double getDestinationLng() { return destinationLng; }
    public void setDestinationLng(Double lng) { this.destinationLng = lng; }
    public Double getDistanceKm() { return distanceKm; }
    public void setDistanceKm(Double km) { this.distanceKm = km; }
    public Integer getEstimatedDurationMinutes() { return estimatedDurationMinutes; }
    public void setEstimatedDurationMinutes(Integer min) { this.estimatedDurationMinutes = min; }
    public String getStatus() { return status; }
    public void setStatus(String status) { this.status = status; }
    public Long getVehicleId() { return vehicleId; }
    public void setVehicleId(Long id) { this.vehicleId = id; }
    public List<RouteWaypoint> getWaypoints() { return waypoints; }
    public void setWaypoints(List<RouteWaypoint> wp) { this.waypoints = wp; }
}

package com.vertexgrid.routes.model;

import com.vertexgrid.shared.model.BaseEntity;
import jakarta.persistence.*;
import java.time.LocalDateTime;

@Entity
@Table(name = "route_waypoints")
public class RouteWaypoint extends BaseEntity {

    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "route_id")
    private Route route;

    @Column(name = "sequence_number", nullable = false)
    private Integer sequenceNumber;

    @Column(nullable = false)
    private Double lat;

    @Column(nullable = false)
    private Double lng;

    @Column(length = 255)
    private String name;

    @Column(name = "estimated_arrival")
    private LocalDateTime estimatedArrival;

    // Getters and setters
    public Route getRoute() { return route; }
    public void setRoute(Route route) { this.route = route; }
    public Integer getSequenceNumber() { return sequenceNumber; }
    public void setSequenceNumber(Integer num) { this.sequenceNumber = num; }
    public Double getLat() { return lat; }
    public void setLat(Double lat) { this.lat = lat; }
    public Double getLng() { return lng; }
    public void setLng(Double lng) { this.lng = lng; }
    public String getName() { return name; }
    public void setName(String name) { this.name = name; }
    public LocalDateTime getEstimatedArrival() { return estimatedArrival; }
    public void setEstimatedArrival(LocalDateTime arr) { this.estimatedArrival = arr; }
}

package com.vertexgrid.tracking.model;

import java.time.Instant;

public class TrackingData {
    private String vehicleId;
    private double lat;
    private double lng;
    private double speed;
    private double heading;
    private Instant timestamp;

    public TrackingData() {}

    public TrackingData(String vehicleId, double lat, double lng, double speed, double heading) {
        this.vehicleId = vehicleId;
        this.lat = lat;
        this.lng = lng;
        this.speed = speed;
        this.heading = heading;
        this.timestamp = Instant.now();
    }

    public String getVehicleId() { return vehicleId; }
    public void setVehicleId(String id) { this.vehicleId = id; }
    public double getLat() { return lat; }
    public void setLat(double lat) { this.lat = lat; }
    public double getLng() { return lng; }
    public void setLng(double lng) { this.lng = lng; }
    public double getSpeed() { return speed; }
    public void setSpeed(double speed) { this.speed = speed; }
    public double getHeading() { return heading; }
    public void setHeading(double heading) { this.heading = heading; }
    public Instant getTimestamp() { return timestamp; }
    public void setTimestamp(Instant timestamp) { this.timestamp = timestamp; }
}

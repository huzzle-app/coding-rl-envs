package com.fleetpulse.tracking.model;


// ViolationEvent extends TrackingEventBase but is not in permits clause
// Fix: Add ViolationEvent to permits clause
public sealed class TrackingEventBase permits
    TrackingEventBase.LocationEvent,
    TrackingEventBase.SpeedEvent,
    TrackingEventBase.GeofenceEvent
    
{
    private final String vehicleId;
    private final long timestamp;

    public TrackingEventBase(String vehicleId) {
        this.vehicleId = vehicleId;
        this.timestamp = System.currentTimeMillis();
    }

    public String getVehicleId() { return vehicleId; }
    public long getTimestamp() { return timestamp; }

    public static final class LocationEvent extends TrackingEventBase {
        private final double lat, lng;
        public LocationEvent(String vehicleId, double lat, double lng) {
            super(vehicleId);
            this.lat = lat;
            this.lng = lng;
        }
        public double getLat() { return lat; }
        public double getLng() { return lng; }
    }

    public static final class SpeedEvent extends TrackingEventBase {
        private final double speed;
        public SpeedEvent(String vehicleId, double speed) {
            super(vehicleId);
            this.speed = speed;
        }
        public double getSpeed() { return speed; }
    }

    public static final class GeofenceEvent extends TrackingEventBase {
        private final String geofenceId;
        private final boolean entered;
        public GeofenceEvent(String vehicleId, String geofenceId, boolean entered) {
            super(vehicleId);
            this.geofenceId = geofenceId;
            this.entered = entered;
        }
        public String getGeofenceId() { return geofenceId; }
        public boolean isEntered() { return entered; }
    }

    
    // Compilation will fail because sealed class doesn't permit this subclass
    // Fix: Add ViolationEvent to the permits clause above
    public static final class ViolationEvent extends TrackingEventBase {
        private final String violationType;
        public ViolationEvent(String vehicleId, String violationType) {
            super(vehicleId);
            this.violationType = violationType;
        }
        public String getViolationType() { return violationType; }
    }
}

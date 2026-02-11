package com.fleetpulse.shared.model;

/**
 * Status enum for FleetPulse microservice health states.
 *
 * Used by service discovery, health checks, and the fleet dashboard
 * to track the operational status of each microservice instance.
 */
public enum ServiceStatus {
    STARTING,
    RUNNING,
    DEGRADED,
    STOPPED,
    ERROR,
    MAINTENANCE;

    /**
     * Returns true if the service is fully healthy and operating normally.
     */
    public boolean isHealthy() {
        return this == RUNNING;
    }

    /**
     * Returns true if the service can accept requests, even if degraded.
     */
    public boolean isAvailable() {
        return this == RUNNING || this == DEGRADED;
    }

    /**
     * Returns true if the service is in a terminal/inactive state.
     */
    public boolean isDown() {
        return this == STOPPED || this == ERROR;
    }

    /**
     * Returns true if the service is transitioning between states.
     */
    public boolean isTransitioning() {
        return this == STARTING || this == MAINTENANCE;
    }
}

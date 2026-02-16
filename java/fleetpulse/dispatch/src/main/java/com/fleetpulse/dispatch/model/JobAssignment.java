package com.fleetpulse.dispatch.model;

/**
 * Record representing a job assignment with required skills.
 *
 * Bugs: K3
 * Category: Templates/Modern Java (record semantics)
 */
// Bug K3: Records generate equals/hashCode based on all fields.
// For array fields, this uses reference equality (==) not content equality.
// Two JobAssignment instances with identical requiredSkills content but
// different array instances will NOT be equal.
// Category: Templates/Modern Java
public record JobAssignment(
    String jobId,
    String vehicleId,
    String driverId,
    String[] requiredSkills,
    long assignedAt
) {
}

package com.vertexgrid.dispatch.model;


// Records generate equals/hashCode based on all fields
// For array fields, this uses reference equality (==) not content equality
// Fix: Don't use arrays in records, use List instead
public record JobAssignment(
    String jobId,
    String vehicleId,
    String driverId,
    String[] requiredSkills,  
    long assignedAt
) {
    
    // but different array instances will NOT be equal
    // Fix: Replace String[] with List<String>
}

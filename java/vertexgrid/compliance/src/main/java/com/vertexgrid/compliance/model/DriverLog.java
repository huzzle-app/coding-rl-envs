package com.vertexgrid.compliance.model;

import com.vertexgrid.shared.model.BaseEntity;
import jakarta.persistence.*;
import java.math.BigDecimal;
import java.time.LocalDate;

/**
 * DriverLog entity representing a daily hours-of-service record for a driver.
 *
 * Tracks driving hours, on-duty hours, off-duty hours, sleeper berth hours,
 * any compliance violations, and the record status. Used by the compliance
 * service to enforce FMCSA Hours of Service regulations.
 */
@Entity
@Table(name = "driver_logs")
public class DriverLog extends BaseEntity {

    @Column(name = "driver_id")
    private Long driverId;

    @Column(name = "log_date", nullable = false)
    private LocalDate logDate;

    @Column(name = "driving_hours", precision = 5, scale = 2)
    private BigDecimal drivingHours = BigDecimal.ZERO;

    @Column(name = "on_duty_hours", precision = 5, scale = 2)
    private BigDecimal onDutyHours = BigDecimal.ZERO;

    @Column(name = "off_duty_hours", precision = 5, scale = 2)
    private BigDecimal offDutyHours = BigDecimal.ZERO;

    @Column(name = "sleeper_hours", precision = 5, scale = 2)
    private BigDecimal sleeperHours = BigDecimal.ZERO;

    @Column
    private String violations;

    @Column(length = 50)
    private String status = "ACTIVE";

    // Getters and setters
    public Long getDriverId() { return driverId; }
    public void setDriverId(Long id) { this.driverId = id; }
    public LocalDate getLogDate() { return logDate; }
    public void setLogDate(LocalDate date) { this.logDate = date; }
    public BigDecimal getDrivingHours() { return drivingHours; }
    public void setDrivingHours(BigDecimal hours) { this.drivingHours = hours; }
    public BigDecimal getOnDutyHours() { return onDutyHours; }
    public void setOnDutyHours(BigDecimal hours) { this.onDutyHours = hours; }
    public BigDecimal getOffDutyHours() { return offDutyHours; }
    public void setOffDutyHours(BigDecimal hours) { this.offDutyHours = hours; }
    public BigDecimal getSleeperHours() { return sleeperHours; }
    public void setSleeperHours(BigDecimal hours) { this.sleeperHours = hours; }
    public String getViolations() { return violations; }
    public void setViolations(String violations) { this.violations = violations; }
    public String getStatus() { return status; }
    public void setStatus(String status) { this.status = status; }
}

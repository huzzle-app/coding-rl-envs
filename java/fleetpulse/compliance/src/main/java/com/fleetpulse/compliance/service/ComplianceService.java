package com.fleetpulse.compliance.service;

import com.fleetpulse.compliance.model.DriverLog;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.List;

/**
 * Service enforcing FMCSA Hours of Service regulations, calculating
 * compliance rates, managing driver bookings, and computing ETAs.
 *
 * Bugs: F9, F10, G5, G6, K4
 * Categories: Precision/Arithmetic, Concurrency, Timezone, Templates
 */
@Service
public class ComplianceService {

    private static final Logger log = LoggerFactory.getLogger(ComplianceService.class);

    private static final BigDecimal MAX_DRIVING_HOURS = new BigDecimal("11.0");
    private static final BigDecimal MAX_ON_DUTY_HOURS = new BigDecimal("14.0");
    private static final BigDecimal MAX_WEEKLY_HOURS = new BigDecimal("60.0");

    /**
     * Calculates remaining driving hours for a driver in the current week.
     *
     * @param weekLogs the driver's logs for the current week
     * @return remaining hours as an integer
     */
    // Bug F9: BigDecimal.intValue() truncates the decimal portion without rounding,
    // losing fractional driving hours.
    // Category: Precision/Arithmetic
    public int calculateRemainingDrivingHours(List<DriverLog> weekLogs) {
        BigDecimal totalDriving = weekLogs.stream()
            .map(DriverLog::getDrivingHours)
            .reduce(BigDecimal.ZERO, BigDecimal::add);

        BigDecimal remaining = MAX_WEEKLY_HOURS.subtract(totalDriving);

        return remaining.intValue();
    }

    /**
     * Calculates the percentage of days a driver was compliant.
     *
     * @param compliantDays number of days within HOS limits
     * @param totalDays     total days in the evaluation period
     * @return compliance rate as a percentage (0-100)
     */
    // Bug F10: Integer division truncates toward zero, so the rate is always 0%
    // unless the driver is 100% compliant.
    // Category: Precision/Arithmetic
    public double calculateComplianceRate(int compliantDays, int totalDays) {
        double rate = compliantDays / totalDays;
        return rate * 100.0;
    }

    /**
     * Books a driver for a time slot if they are available.
     *
     * @param driverId     the driver to book
     * @param start        the booking start time
     * @param end          the booking end time
     * @param existingLogs the driver's current log entries (checked for overlap)
     * @return true if the driver was booked, false if unavailable
     */
    // Bug G5: Check-then-act race condition allows double-booking when two
    // dispatchers call bookDriver() concurrently.
    // Category: Concurrency
    public boolean bookDriver(Long driverId, LocalDateTime start, LocalDateTime end,
                               List<DriverLog> existingLogs) {
        boolean available = existingLogs.stream()
            .noneMatch(driverLog -> isOverlapping(driverLog, start, end));

        if (available) {
            DriverLog newLog = new DriverLog();
            newLog.setDriverId(driverId);
            newLog.setLogDate(start.toLocalDate());
            newLog.setStatus("BOOKED");
            existingLogs.add(newLog);
            return true;
        }
        return false;
    }

    /**
     * Calculates estimated time of arrival by adding duration to departure time.
     *
     * @param departureTime  the departure time (timezone-naive)
     * @param durationMinutes travel duration in minutes
     * @param timezone        the departure timezone identifier (e.g., "America/New_York")
     * @return the estimated arrival time (timezone-naive, possibly incorrect)
     */
    // Bug G6: LocalDateTime carries no timezone information. Adding minutes
    // ignores timezone differences between departure and arrival locations.
    // Category: Timezone
    public LocalDateTime calculateETA(LocalDateTime departureTime, int durationMinutes, String timezone) {
        return departureTime.plusMinutes(durationMinutes);
    }

    /**
     * Checks a driver's logs for HOS violations (excess driving or on-duty hours).
     *
     * @param driverId the driver ID
     * @param logs     the driver's logs to check
     * @return list of violation description strings
     */
    // Bug K4: When called from a virtual thread, the synchronized keyword pins
    // the carrier thread for the entire method duration including blocking I/O.
    // Category: Concurrency/Virtual Threads
    public synchronized List<String> checkComplianceViolations(Long driverId, List<DriverLog> logs) {
        List<String> violations = new ArrayList<>();

        for (DriverLog driverLog : logs) {
            if (driverLog.getDrivingHours().compareTo(MAX_DRIVING_HOURS) > 0) {
                violations.add("EXCESS_DRIVING: " + driverLog.getDrivingHours() + "h on " + driverLog.getLogDate());
            }
            if (driverLog.getOnDutyHours().compareTo(MAX_ON_DUTY_HOURS) > 0) {
                violations.add("EXCESS_ON_DUTY: " + driverLog.getOnDutyHours() + "h on " + driverLog.getLogDate());
            }
        }

        // Simulate database I/O (loading additional compliance data)
        try { Thread.sleep(50); } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
        }

        return violations;
    }

    /**
     * Checks whether a time range overlaps with a driver log's driving period.
     */
    private boolean isOverlapping(DriverLog driverLog, LocalDateTime start, LocalDateTime end) {
        LocalDateTime logStart = driverLog.getLogDate().atStartOfDay();
        LocalDateTime logEnd = logStart.plusHours(driverLog.getDrivingHours().longValue());
        return !start.isAfter(logEnd) && !end.isBefore(logStart);
    }

    /**
     * Checks whether a driver's weekly driving hours are within the legal limit.
     *
     * @param weekLogs the driver's logs for the current week
     * @return true if the driver is compliant (at or below 60 weekly hours)
     */
    public boolean isDriverCompliant(List<DriverLog> weekLogs) {
        BigDecimal totalDriving = weekLogs.stream()
            .map(DriverLog::getDrivingHours)
            .reduce(BigDecimal.ZERO, BigDecimal::add);

        return totalDriving.compareTo(MAX_WEEKLY_HOURS) <= 0;
    }
}

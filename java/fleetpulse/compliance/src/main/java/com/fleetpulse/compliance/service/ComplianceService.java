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
 * Contains intentional bugs:
 *   F9  - Duration overflow (BigDecimal to int loses decimal precision)
 *   F10 - Rate calculation precision (integer division truncates to zero)
 *   G5  - Booking race condition (check-then-act without synchronization)
 *   G6  - ETA calculation timezone error (LocalDateTime has no timezone)
 *   K4  - Virtual thread pinning on synchronized (blocks carrier thread)
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
    
    // BigDecimal.intValue() truncates the decimal portion without rounding.
    // A driver with 52.75 hours driven has 7.25 remaining hours, but intValue()
    // returns 7, losing 15 minutes of allowed driving time. Worse, if remaining
    // is negative (driver over limit), large negative values can overflow int range.
    // Fix: Use proper rounding and check for overflow:
    //   return remaining.setScale(0, RoundingMode.FLOOR).intValueExact();
    //   Or better, return BigDecimal to preserve precision.
    public int calculateRemainingDrivingHours(List<DriverLog> weekLogs) {
        BigDecimal totalDriving = weekLogs.stream()
            .map(DriverLog::getDrivingHours)
            .reduce(BigDecimal.ZERO, BigDecimal::add);

        BigDecimal remaining = MAX_WEEKLY_HOURS.subtract(totalDriving);

        
        // e.g., 7.25 remaining hours becomes 7, losing 15 minutes
        return remaining.intValue();
    }

    /**
     * Calculates the percentage of days a driver was compliant.
     *
     * @param compliantDays number of days within HOS limits
     * @param totalDays     total days in the evaluation period
     * @return compliance rate as a percentage (0-100)
     */
    
    // Java integer division truncates toward zero. When compliantDays < totalDays,
    // the division yields 0 (e.g., 9/10 = 0 in integer math). Multiplying 0 by
    // 100.0 still gives 0.0, so the compliance rate is always 0% unless the driver
    // is 100% compliant.
    // Fix: Cast to double before dividing:
    //   double rate = (double) compliantDays / totalDays;
    //   return rate * 100.0;
    public double calculateComplianceRate(int compliantDays, int totalDays) {
        
        // e.g., 9 / 10 = 0 in integer arithmetic, not 0.9
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
    
    // Two dispatchers calling bookDriver() concurrently can both see the driver
    // as available (the noneMatch check passes for both), and both proceed to
    // add a booking. This results in double-booking the same driver for
    // overlapping time slots.
    // Fix: Use optimistic locking with @Version, or a database-level constraint
    //       (UNIQUE on driver_id + time range), or synchronized/ReentrantLock:
    //   Use SELECT ... FOR UPDATE in a transaction, or
    //   Add a unique constraint and handle ConstraintViolationException
    public boolean bookDriver(Long driverId, LocalDateTime start, LocalDateTime end,
                               List<DriverLog> existingLogs) {
        
        // between checking availability and creating the booking,
        // another thread could book the same driver for the same slot
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
    
    // departureTime is a LocalDateTime which carries no timezone information.
    // Simply adding minutes to it ignores timezone differences between departure
    // and arrival locations, DST transitions, and UTC offset changes. A 3-hour
    // flight from New York to Los Angeles would show an arrival 3 hours after
    // departure in NYC time, but the actual local arrival time should account
    // for the 3-hour timezone difference.
    // Fix: Use ZonedDateTime consistently:
    //   ZonedDateTime departure = departureTime.atZone(ZoneId.of(timezone));
    //   return departure.plusMinutes(durationMinutes).toLocalDateTime();
    public LocalDateTime calculateETA(LocalDateTime departureTime, int durationMinutes, String timezone) {
        
        // Adding duration without timezone conversion gives wrong result
        // when departure and arrival are in different timezones
        return departureTime.plusMinutes(durationMinutes);
    }

    /**
     * Checks a driver's logs for HOS violations (excess driving or on-duty hours).
     *
     * @param driverId the driver ID
     * @param logs     the driver's logs to check
     * @return list of violation description strings
     */
    
    // When this method is called from a virtual thread (Project Loom), the
    // synchronized keyword pins the virtual thread to its carrier platform thread.
    // Since the method body performs blocking I/O (Thread.sleep simulating DB access),
    // the carrier thread is blocked and cannot run other virtual threads. Under load,
    // this exhausts the carrier thread pool and defeats the purpose of virtual threads.
    // Fix: Replace synchronized with ReentrantLock which supports virtual thread unmounting:
    //   private final ReentrantLock complianceLock = new ReentrantLock();
    //   public List<String> checkComplianceViolations(...) {
    //       complianceLock.lock();
    //       try { ... } finally { complianceLock.unlock(); }
    //   }
    public synchronized List<String> checkComplianceViolations(Long driverId, List<DriverLog> logs) {
        
        // If called from a virtual thread, this pins the carrier thread for the
        // entire duration, including the simulated database I/O below
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

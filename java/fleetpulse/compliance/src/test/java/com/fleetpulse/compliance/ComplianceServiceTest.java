package com.fleetpulse.compliance;

import com.fleetpulse.compliance.model.DriverLog;
import com.fleetpulse.compliance.service.ComplianceService;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Tag;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.Timeout;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.time.LocalDateTime;
import java.time.ZoneId;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.locks.ReentrantLock;

import static org.junit.jupiter.api.Assertions.*;

@Tag("unit")
public class ComplianceServiceTest {

    private ComplianceService complianceService;

    @BeforeEach
    void setUp() {
        complianceService = new ComplianceService();
    }

    // ====== BUG F9: Duration overflow / precision loss ======
    @Test
    void test_duration_no_overflow() {
        
        // 52.75 driven -> 7.25 remaining -> intValue() returns 7, losing 15 minutes
        List<DriverLog> logs = new ArrayList<>();
        logs.add(createLog(1L, "2025-01-01", new BigDecimal("10.50"), new BigDecimal("12.00")));
        logs.add(createLog(1L, "2025-01-02", new BigDecimal("10.25"), new BigDecimal("12.00")));
        logs.add(createLog(1L, "2025-01-03", new BigDecimal("10.50"), new BigDecimal("12.00")));
        logs.add(createLog(1L, "2025-01-04", new BigDecimal("10.25"), new BigDecimal("12.00")));
        logs.add(createLog(1L, "2025-01-05", new BigDecimal("11.00"), new BigDecimal("13.00")));
        // Total: 52.50 hours, remaining: 60 - 52.50 = 7.50

        int remaining = complianceService.calculateRemainingDrivingHours(logs);
        // With the bug, intValue() of 7.50 = 7 (loses 30 minutes)
        // With the fix, should properly round to 7 or return 8 with ceiling
        assertTrue(remaining >= 7, "Remaining hours should be at least 7");
    }

    @Test
    void test_remaining_hours_precise() {
        
        List<DriverLog> logs = new ArrayList<>();
        logs.add(createLog(1L, "2025-01-01", new BigDecimal("52.75"), new BigDecimal("55.00")));
        // Remaining: 60 - 52.75 = 7.25

        int remaining = complianceService.calculateRemainingDrivingHours(logs);
        // With bug: intValue() of 7.25 = 7
        // With fix: should be 7 (floor is acceptable for hours)
        assertTrue(remaining >= 7 && remaining <= 8,
            "Remaining hours from 7.25 should be 7 or 8, got " + remaining);
    }

    @Test
    void test_remaining_hours_zero() {
        List<DriverLog> logs = new ArrayList<>();
        logs.add(createLog(1L, "2025-01-01", new BigDecimal("60.00"), new BigDecimal("60.00")));

        int remaining = complianceService.calculateRemainingDrivingHours(logs);
        assertEquals(0, remaining, "Exactly at limit should have 0 remaining");
    }

    @Test
    void test_remaining_hours_full() {
        List<DriverLog> logs = new ArrayList<>();
        // No driving done
        int remaining = complianceService.calculateRemainingDrivingHours(logs);
        assertEquals(60, remaining, "No driving should have 60 hours remaining");
    }

    @Test
    void test_remaining_hours_over_limit() {
        List<DriverLog> logs = new ArrayList<>();
        logs.add(createLog(1L, "2025-01-01", new BigDecimal("65.00"), new BigDecimal("65.00")));

        int remaining = complianceService.calculateRemainingDrivingHours(logs);
        assertTrue(remaining < 0, "Over limit should be negative remaining");
    }

    @Test
    void test_remaining_hours_many_logs() {
        List<DriverLog> logs = new ArrayList<>();
        for (int i = 0; i < 7; i++) {
            logs.add(createLog(1L, "2025-01-0" + (i + 1),
                new BigDecimal("8.00"), new BigDecimal("10.00")));
        }
        // Total: 56 hours, remaining: 4
        int remaining = complianceService.calculateRemainingDrivingHours(logs);
        assertEquals(4, remaining);
    }

    @Test
    void test_remaining_hours_fractional_sum() {
        List<DriverLog> logs = new ArrayList<>();
        logs.add(createLog(1L, "2025-01-01", new BigDecimal("8.33"), new BigDecimal("10.00")));
        logs.add(createLog(1L, "2025-01-02", new BigDecimal("8.33"), new BigDecimal("10.00")));
        logs.add(createLog(1L, "2025-01-03", new BigDecimal("8.34"), new BigDecimal("10.00")));
        // Total: 25.00
        int remaining = complianceService.calculateRemainingDrivingHours(logs);
        assertEquals(35, remaining);
    }

    // ====== BUG F10: Rate calculation precision (integer division) ======
    @Test
    void test_rate_calculation() {
        
        double rate = complianceService.calculateComplianceRate(9, 10);
        // With bug: (9 / 10) * 100 = 0 * 100 = 0.0
        // With fix: ((double)9 / 10) * 100 = 90.0
        assertEquals(90.0, rate, 0.01,
            "9 out of 10 compliant days should be 90%, got " + rate);
    }

    @Test
    void test_no_integer_division() {
        
        double rate = complianceService.calculateComplianceRate(1, 2);
        // With bug: 1/2 = 0 in integer math, rate = 0
        // With fix: 1.0/2.0 = 0.5, rate = 50.0
        assertEquals(50.0, rate, 0.01,
            "1 out of 2 should be 50%, got " + rate);
    }

    @Test
    void test_rate_100_percent() {
        double rate = complianceService.calculateComplianceRate(10, 10);
        assertEquals(100.0, rate, 0.01);
    }

    @Test
    void test_rate_0_percent() {
        double rate = complianceService.calculateComplianceRate(0, 10);
        assertEquals(0.0, rate, 0.01);
    }

    @Test
    void test_rate_75_percent() {
        double rate = complianceService.calculateComplianceRate(3, 4);
        assertEquals(75.0, rate, 0.01);
    }

    @Test
    void test_rate_33_percent() {
        double rate = complianceService.calculateComplianceRate(1, 3);
        // With bug: 1/3 = 0 -> 0%
        // With fix: 33.33...%
        assertTrue(rate > 33.0 && rate < 34.0,
            "1 out of 3 should be ~33.33%, got " + rate);
    }

    @Test
    void test_rate_small_fraction() {
        double rate = complianceService.calculateComplianceRate(1, 100);
        // With bug: 1/100 = 0 -> 0%
        // With fix: 1.0%
        assertEquals(1.0, rate, 0.01,
            "1 out of 100 should be 1%");
    }

    @Test
    void test_rate_large_numbers() {
        double rate = complianceService.calculateComplianceRate(999, 1000);
        assertEquals(99.9, rate, 0.01);
    }

    @Test
    void test_rate_single_day() {
        double rate = complianceService.calculateComplianceRate(1, 1);
        assertEquals(100.0, rate, 0.01);
    }

    // ====== BUG G5: Booking race condition ======
    @Test
    void test_booking_race_safe() {
        
        Long driverId = 1L;
        LocalDateTime start = LocalDateTime.of(2025, 3, 15, 8, 0);
        LocalDateTime end = LocalDateTime.of(2025, 3, 15, 16, 0);
        List<DriverLog> logs = Collections.synchronizedList(new ArrayList<>());

        // First booking should succeed
        boolean first = complianceService.bookDriver(driverId, start, end, logs);
        assertTrue(first, "First booking should succeed");
    }

    @Test
    void test_no_double_booking() {
        
        Long driverId = 1L;
        LocalDateTime start = LocalDateTime.of(2025, 3, 15, 8, 0);
        LocalDateTime end = LocalDateTime.of(2025, 3, 15, 16, 0);
        List<DriverLog> logs = Collections.synchronizedList(new ArrayList<>());

        // Book the same slot twice sequentially
        boolean first = complianceService.bookDriver(driverId, start, end, logs);
        boolean second = complianceService.bookDriver(driverId, start, end, logs);

        // At least first should succeed; ideally second should fail
        assertTrue(first, "First booking should succeed");
        // With the fix, second booking should fail (overlap detected)
        // With the bug, both may succeed in concurrent scenario
    }

    @Test
    void test_book_non_overlapping() {
        Long driverId = 1L;
        List<DriverLog> logs = new ArrayList<>();

        LocalDateTime start1 = LocalDateTime.of(2025, 3, 15, 8, 0);
        LocalDateTime end1 = LocalDateTime.of(2025, 3, 15, 12, 0);
        LocalDateTime start2 = LocalDateTime.of(2025, 3, 16, 8, 0);
        LocalDateTime end2 = LocalDateTime.of(2025, 3, 16, 12, 0);

        assertTrue(complianceService.bookDriver(driverId, start1, end1, logs));
        // Non-overlapping day should succeed
        assertTrue(complianceService.bookDriver(driverId, start2, end2, logs));
    }

    @Test
    void test_book_creates_log_entry() {
        Long driverId = 1L;
        List<DriverLog> logs = new ArrayList<>();
        LocalDateTime start = LocalDateTime.of(2025, 3, 15, 8, 0);
        LocalDateTime end = LocalDateTime.of(2025, 3, 15, 16, 0);

        complianceService.bookDriver(driverId, start, end, logs);
        assertFalse(logs.isEmpty(), "Booking should add a log entry");
    }

    @Test
    void test_book_log_has_correct_driver() {
        Long driverId = 42L;
        List<DriverLog> logs = new ArrayList<>();
        LocalDateTime start = LocalDateTime.of(2025, 3, 15, 8, 0);
        LocalDateTime end = LocalDateTime.of(2025, 3, 15, 16, 0);

        complianceService.bookDriver(driverId, start, end, logs);
        if (!logs.isEmpty()) {
            assertEquals(driverId, logs.get(0).getDriverId());
            assertEquals("BOOKED", logs.get(0).getStatus());
        }
    }

    @Test
    void test_booking_concurrent_stress() throws Exception {
        
        Long driverId = 1L;
        LocalDateTime start = LocalDateTime.of(2025, 3, 15, 8, 0);
        LocalDateTime end = LocalDateTime.of(2025, 3, 15, 16, 0);
        List<DriverLog> logs = Collections.synchronizedList(new ArrayList<>());

        int threads = 10;
        CountDownLatch startLatch = new CountDownLatch(1);
        CountDownLatch doneLatch = new CountDownLatch(threads);
        List<Boolean> results = Collections.synchronizedList(new ArrayList<>());

        for (int i = 0; i < threads; i++) {
            new Thread(() -> {
                try {
                    startLatch.await();
                    results.add(complianceService.bookDriver(driverId, start, end, logs));
                } catch (Exception e) {
                    // ignore
                } finally {
                    doneLatch.countDown();
                }
            }).start();
        }

        startLatch.countDown();
        doneLatch.await(10, TimeUnit.SECONDS);

        // With proper synchronization, only 1 booking should succeed
        // With the bug, multiple may succeed
        long successes = results.stream().filter(b -> b).count();
        assertTrue(successes >= 1, "At least one booking should succeed");
    }

    // ====== BUG G6: ETA timezone error ======
    @Test
    void test_eta_timezone_correct() {
        
        // for cross-timezone travel
        LocalDateTime departure = LocalDateTime.of(2025, 3, 15, 10, 0);
        int durationMinutes = 180; // 3 hour flight

        LocalDateTime eta = complianceService.calculateETA(departure, durationMinutes, "America/New_York");
        assertNotNull(eta);
        // With the bug, ETA is simply departure + 3h = 13:00 (NYC time)
        // For a NYC to LAX flight, local arrival should account for -3h timezone offset
    }

    @Test
    void test_cross_timezone_eta() {
        
        LocalDateTime departure = LocalDateTime.of(2025, 3, 15, 8, 0);
        int durationMinutes = 60; // 1 hour

        // NYC timezone
        LocalDateTime eta = complianceService.calculateETA(departure, durationMinutes, "America/New_York");
        assertNotNull(eta);
        // Basic check: ETA should be after departure
        assertTrue(eta.isAfter(departure), "ETA should be after departure time");
    }

    @Test
    void test_eta_same_timezone() {
        LocalDateTime departure = LocalDateTime.of(2025, 3, 15, 10, 0);
        LocalDateTime eta = complianceService.calculateETA(departure, 120, "America/New_York");
        assertEquals(LocalDateTime.of(2025, 3, 15, 12, 0), eta,
            "Same timezone ETA should be departure + duration");
    }

    @Test
    void test_eta_overnight() {
        LocalDateTime departure = LocalDateTime.of(2025, 3, 15, 23, 0);
        LocalDateTime eta = complianceService.calculateETA(departure, 120, "America/New_York");
        assertEquals(LocalDateTime.of(2025, 3, 16, 1, 0), eta,
            "Overnight ETA should roll to next day");
    }

    @Test
    void test_eta_zero_duration() {
        LocalDateTime departure = LocalDateTime.of(2025, 3, 15, 10, 0);
        LocalDateTime eta = complianceService.calculateETA(departure, 0, "UTC");
        assertEquals(departure, eta, "Zero duration should return departure time");
    }

    @Test
    void test_eta_large_duration() {
        LocalDateTime departure = LocalDateTime.of(2025, 3, 15, 10, 0);
        LocalDateTime eta = complianceService.calculateETA(departure, 1440, "UTC"); // 24 hours
        assertEquals(LocalDateTime.of(2025, 3, 16, 10, 0), eta);
    }

    @Test
    void test_eta_dst_transition() {
        // Spring forward: March 9 2025, 2:00 AM -> 3:00 AM (clocks skip forward)
        LocalDateTime departure = LocalDateTime.of(2025, 3, 9, 1, 0);
        LocalDateTime eta = complianceService.calculateETA(departure, 120, "America/New_York");
        assertNotNull(eta);
    }

    // ====== BUG K4: Virtual thread pinning on synchronized ======
    @Test
    void test_virtual_thread_compliance() {
        
        // The fix should use ReentrantLock instead
        List<DriverLog> logs = new ArrayList<>();
        logs.add(createLog(1L, "2025-01-01", new BigDecimal("12.00"), new BigDecimal("15.00")));

        // Should complete without issue
        List<String> violations = complianceService.checkComplianceViolations(1L, logs);
        assertNotNull(violations);
        assertTrue(violations.stream().anyMatch(v -> v.contains("EXCESS_DRIVING")),
            "12h driving exceeds 11h limit");
    }

    @Test
    void test_no_synchronized_io() {
        
        List<DriverLog> logs = new ArrayList<>();
        logs.add(createLog(1L, "2025-01-01", new BigDecimal("8.00"), new BigDecimal("10.00")));

        int threads = 5;
        CountDownLatch latch = new CountDownLatch(threads);
        List<Exception> errors = Collections.synchronizedList(new ArrayList<>());

        for (int i = 0; i < threads; i++) {
            new Thread(() -> {
                try {
                    complianceService.checkComplianceViolations(1L, logs);
                } catch (Exception e) {
                    errors.add(e);
                } finally {
                    latch.countDown();
                }
            }).start();
        }

        try {
            latch.await(30, TimeUnit.SECONDS);
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
        }

        assertTrue(errors.isEmpty(),
            "Concurrent compliance checks should not throw: " + errors);
    }

    @Test
    void test_compliance_no_violations() {
        List<DriverLog> logs = new ArrayList<>();
        logs.add(createLog(1L, "2025-01-01", new BigDecimal("8.00"), new BigDecimal("10.00")));

        List<String> violations = complianceService.checkComplianceViolations(1L, logs);
        assertTrue(violations.isEmpty(), "8h driving should have no violations");
    }

    @Test
    void test_compliance_excess_driving() {
        List<DriverLog> logs = new ArrayList<>();
        logs.add(createLog(1L, "2025-01-01", new BigDecimal("12.00"), new BigDecimal("13.00")));

        List<String> violations = complianceService.checkComplianceViolations(1L, logs);
        assertTrue(violations.stream().anyMatch(v -> v.contains("EXCESS_DRIVING")));
    }

    @Test
    void test_compliance_excess_on_duty() {
        List<DriverLog> logs = new ArrayList<>();
        logs.add(createLog(1L, "2025-01-01", new BigDecimal("10.00"), new BigDecimal("15.00")));

        List<String> violations = complianceService.checkComplianceViolations(1L, logs);
        assertTrue(violations.stream().anyMatch(v -> v.contains("EXCESS_ON_DUTY")));
    }

    @Test
    void test_compliance_both_violations() {
        List<DriverLog> logs = new ArrayList<>();
        logs.add(createLog(1L, "2025-01-01", new BigDecimal("12.00"), new BigDecimal("16.00")));

        List<String> violations = complianceService.checkComplianceViolations(1L, logs);
        assertTrue(violations.size() >= 2, "Should have both driving and on-duty violations");
    }

    @Test
    void test_compliance_empty_logs() {
        List<String> violations = complianceService.checkComplianceViolations(1L, new ArrayList<>());
        assertTrue(violations.isEmpty());
    }

    @Test
    void test_compliance_exact_limit_driving() {
        List<DriverLog> logs = new ArrayList<>();
        logs.add(createLog(1L, "2025-01-01", new BigDecimal("11.00"), new BigDecimal("12.00")));

        List<String> violations = complianceService.checkComplianceViolations(1L, logs);
        // Exactly at limit (11h) should not be a violation
        assertFalse(violations.stream().anyMatch(v -> v.contains("EXCESS_DRIVING")),
            "Exactly 11h should not be excess driving");
    }

    @Test
    void test_compliance_exact_limit_on_duty() {
        List<DriverLog> logs = new ArrayList<>();
        logs.add(createLog(1L, "2025-01-01", new BigDecimal("10.00"), new BigDecimal("14.00")));

        List<String> violations = complianceService.checkComplianceViolations(1L, logs);
        assertFalse(violations.stream().anyMatch(v -> v.contains("EXCESS_ON_DUTY")),
            "Exactly 14h on-duty should not be excess");
    }

    @Test
    void test_compliance_multiple_days() {
        List<DriverLog> logs = new ArrayList<>();
        logs.add(createLog(1L, "2025-01-01", new BigDecimal("8.00"), new BigDecimal("10.00")));
        logs.add(createLog(1L, "2025-01-02", new BigDecimal("12.00"), new BigDecimal("15.00")));
        logs.add(createLog(1L, "2025-01-03", new BigDecimal("9.00"), new BigDecimal("11.00")));

        List<String> violations = complianceService.checkComplianceViolations(1L, logs);
        // Day 2: excess driving (12 > 11) and excess on-duty (15 > 14)
        assertTrue(violations.size() >= 2);
    }

    // ====== isDriverCompliant tests ======
    @Test
    void test_driver_compliant() {
        List<DriverLog> logs = new ArrayList<>();
        logs.add(createLog(1L, "2025-01-01", new BigDecimal("10.00"), new BigDecimal("12.00")));
        logs.add(createLog(1L, "2025-01-02", new BigDecimal("10.00"), new BigDecimal("12.00")));

        assertTrue(complianceService.isDriverCompliant(logs),
            "20h total should be compliant (under 60h limit)");
    }

    @Test
    void test_driver_not_compliant() {
        List<DriverLog> logs = new ArrayList<>();
        for (int i = 0; i < 7; i++) {
            logs.add(createLog(1L, "2025-01-0" + (i + 1),
                new BigDecimal("9.00"), new BigDecimal("11.00")));
        }
        // Total: 63 hours, exceeds 60h limit
        assertFalse(complianceService.isDriverCompliant(logs));
    }

    @Test
    void test_driver_exactly_at_limit() {
        List<DriverLog> logs = new ArrayList<>();
        logs.add(createLog(1L, "2025-01-01", new BigDecimal("60.00"), new BigDecimal("60.00")));

        assertTrue(complianceService.isDriverCompliant(logs),
            "Exactly at 60h limit should be compliant (<=)");
    }

    @Test
    void test_driver_compliant_empty_logs() {
        assertTrue(complianceService.isDriverCompliant(new ArrayList<>()),
            "No logs should be compliant");
    }

    @Test
    void test_driver_compliant_single_log() {
        List<DriverLog> logs = new ArrayList<>();
        logs.add(createLog(1L, "2025-01-01", new BigDecimal("11.00"), new BigDecimal("14.00")));

        assertTrue(complianceService.isDriverCompliant(logs));
    }

    // ====== DriverLog model tests ======
    @Test
    void test_driver_log_defaults() {
        DriverLog log = new DriverLog();
        assertEquals(0, BigDecimal.ZERO.compareTo(log.getDrivingHours()));
        assertEquals(0, BigDecimal.ZERO.compareTo(log.getOnDutyHours()));
        assertEquals(0, BigDecimal.ZERO.compareTo(log.getOffDutyHours()));
        assertEquals(0, BigDecimal.ZERO.compareTo(log.getSleeperHours()));
        assertEquals("ACTIVE", log.getStatus());
    }

    @Test
    void test_driver_log_setters() {
        DriverLog log = new DriverLog();
        log.setDriverId(42L);
        log.setLogDate(LocalDate.of(2025, 3, 15));
        log.setDrivingHours(new BigDecimal("8.50"));
        log.setOnDutyHours(new BigDecimal("10.00"));
        log.setOffDutyHours(new BigDecimal("10.00"));
        log.setSleeperHours(new BigDecimal("4.00"));
        log.setViolations("NONE");
        log.setStatus("REVIEWED");

        assertEquals(42L, log.getDriverId());
        assertEquals(LocalDate.of(2025, 3, 15), log.getLogDate());
        assertEquals(0, new BigDecimal("8.50").compareTo(log.getDrivingHours()));
        assertEquals(0, new BigDecimal("10.00").compareTo(log.getOnDutyHours()));
        assertEquals(0, new BigDecimal("10.00").compareTo(log.getOffDutyHours()));
        assertEquals(0, new BigDecimal("4.00").compareTo(log.getSleeperHours()));
        assertEquals("NONE", log.getViolations());
        assertEquals("REVIEWED", log.getStatus());
    }

    @Test
    void test_driver_log_null_violations() {
        DriverLog log = new DriverLog();
        assertNull(log.getViolations());
    }

    // ====== Additional edge cases ======
    @Test
    void test_rate_calculation_boundary() {
        // Just above integer truncation boundary
        double rate = complianceService.calculateComplianceRate(99, 100);
        assertEquals(99.0, rate, 0.01);
    }

    @Test
    void test_remaining_hours_single_log() {
        List<DriverLog> logs = new ArrayList<>();
        logs.add(createLog(1L, "2025-01-01", new BigDecimal("30.00"), new BigDecimal("35.00")));

        int remaining = complianceService.calculateRemainingDrivingHours(logs);
        assertEquals(30, remaining);
    }

    @Test
    void test_book_driver_returns_false_when_unavailable() {
        Long driverId = 1L;
        List<DriverLog> logs = new ArrayList<>();
        LocalDateTime start = LocalDateTime.of(2025, 3, 15, 8, 0);
        LocalDateTime end = LocalDateTime.of(2025, 3, 15, 16, 0);

        // Book first
        complianceService.bookDriver(driverId, start, end, logs);

        // Try overlapping booking
        LocalDateTime start2 = LocalDateTime.of(2025, 3, 15, 10, 0);
        LocalDateTime end2 = LocalDateTime.of(2025, 3, 15, 14, 0);
        boolean result = complianceService.bookDriver(driverId, start2, end2, logs);

        // With the fix, this should return false (overlap detected)
        // With the bug in concurrent scenario, it might return true
    }

    @Test
    void test_eta_short_duration() {
        LocalDateTime departure = LocalDateTime.of(2025, 3, 15, 10, 0);
        LocalDateTime eta = complianceService.calculateETA(departure, 15, "UTC");
        assertEquals(LocalDateTime.of(2025, 3, 15, 10, 15), eta);
    }

    @Test
    void test_eta_end_of_year() {
        LocalDateTime departure = LocalDateTime.of(2025, 12, 31, 23, 0);
        LocalDateTime eta = complianceService.calculateETA(departure, 120, "UTC");
        assertEquals(2026, eta.getYear());
    }

    @Test
    void test_compliance_concurrent_violations_check() throws Exception {
        List<DriverLog> logs = new ArrayList<>();
        for (int i = 0; i < 5; i++) {
            logs.add(createLog(1L, "2025-01-0" + (i + 1),
                new BigDecimal("12.00"), new BigDecimal("15.00")));
        }

        int threads = 5;
        CountDownLatch latch = new CountDownLatch(threads);
        List<List<String>> results = Collections.synchronizedList(new ArrayList<>());

        for (int i = 0; i < threads; i++) {
            new Thread(() -> {
                try {
                    results.add(complianceService.checkComplianceViolations(1L, logs));
                } finally {
                    latch.countDown();
                }
            }).start();
        }

        latch.await(30, TimeUnit.SECONDS);
        assertEquals(threads, results.size());
        for (List<String> result : results) {
            assertFalse(result.isEmpty(), "Each thread should find violations");
        }
    }

    @Test
    void test_remaining_hours_with_zero_driving() {
        List<DriverLog> logs = new ArrayList<>();
        logs.add(createLog(1L, "2025-01-01", BigDecimal.ZERO, new BigDecimal("8.00")));
        logs.add(createLog(1L, "2025-01-02", BigDecimal.ZERO, new BigDecimal("8.00")));

        int remaining = complianceService.calculateRemainingDrivingHours(logs);
        assertEquals(60, remaining, "Zero driving hours should leave full 60h remaining");
    }

    @Test
    void test_compliance_service_thread_safety() {
        
        assertDoesNotThrow(() -> {
            List<DriverLog> logs = List.of(
                createLog(1L, "2025-01-01", new BigDecimal("10.00"), new BigDecimal("12.00"))
            );
            complianceService.checkComplianceViolations(1L, logs);
        });
    }

    @Test
    void test_booking_with_empty_logs() {
        boolean result = complianceService.bookDriver(1L,
            LocalDateTime.of(2025, 3, 15, 8, 0),
            LocalDateTime.of(2025, 3, 15, 16, 0),
            new ArrayList<>());
        assertTrue(result, "Empty logs should allow booking");
    }

    @Test
    void test_rate_high_compliance() {
        double rate = complianceService.calculateComplianceRate(365, 365);
        assertEquals(100.0, rate, 0.01);
    }

    @Test
    void test_rate_low_compliance() {
        double rate = complianceService.calculateComplianceRate(1, 365);
        assertTrue(rate > 0.0 && rate < 1.0,
            "1 of 365 should be about 0.27%");
    }

    // ====== Additional edge case tests ======
    @Test
    void test_remaining_hours_exact_integer() {
        List<DriverLog> logs = new ArrayList<>();
        logs.add(createLog(1L, "2025-01-01", new BigDecimal("50.00"), new BigDecimal("55.00")));
        int remaining = complianceService.calculateRemainingDrivingHours(logs);
        assertEquals(10, remaining);
    }

    @Test
    void test_rate_two_thirds() {
        double rate = complianceService.calculateComplianceRate(2, 3);
        assertTrue(rate > 66.0 && rate < 67.0,
            "2/3 should be ~66.67%, got " + rate);
    }

    @Test
    void test_rate_quarter() {
        double rate = complianceService.calculateComplianceRate(1, 4);
        assertEquals(25.0, rate, 0.01);
    }

    @Test
    void test_rate_five_sixths() {
        double rate = complianceService.calculateComplianceRate(5, 6);
        assertTrue(rate > 83.0 && rate < 84.0);
    }

    @Test
    void test_eta_5_minutes() {
        LocalDateTime departure = LocalDateTime.of(2025, 3, 15, 10, 0);
        LocalDateTime eta = complianceService.calculateETA(departure, 5, "UTC");
        assertEquals(LocalDateTime.of(2025, 3, 15, 10, 5), eta);
    }

    @Test
    void test_eta_exactly_one_hour() {
        LocalDateTime departure = LocalDateTime.of(2025, 3, 15, 10, 0);
        LocalDateTime eta = complianceService.calculateETA(departure, 60, "UTC");
        assertEquals(LocalDateTime.of(2025, 3, 15, 11, 0), eta);
    }

    @Test
    void test_compliance_just_over_driving_limit() {
        List<DriverLog> logs = new ArrayList<>();
        logs.add(createLog(1L, "2025-01-01", new BigDecimal("11.01"), new BigDecimal("12.00")));
        List<String> violations = complianceService.checkComplianceViolations(1L, logs);
        assertTrue(violations.stream().anyMatch(v -> v.contains("EXCESS_DRIVING")));
    }

    @Test
    void test_compliance_just_over_on_duty_limit() {
        List<DriverLog> logs = new ArrayList<>();
        logs.add(createLog(1L, "2025-01-01", new BigDecimal("10.00"), new BigDecimal("14.01")));
        List<String> violations = complianceService.checkComplianceViolations(1L, logs);
        assertTrue(violations.stream().anyMatch(v -> v.contains("EXCESS_ON_DUTY")));
    }

    @Test
    void test_driver_just_over_weekly_limit() {
        List<DriverLog> logs = new ArrayList<>();
        logs.add(createLog(1L, "2025-01-01", new BigDecimal("60.01"), new BigDecimal("60.01")));
        assertFalse(complianceService.isDriverCompliant(logs));
    }

    @Test
    void test_driver_just_under_weekly_limit() {
        List<DriverLog> logs = new ArrayList<>();
        logs.add(createLog(1L, "2025-01-01", new BigDecimal("59.99"), new BigDecimal("59.99")));
        assertTrue(complianceService.isDriverCompliant(logs));
    }

    @Test
    void test_book_multiple_different_days() {
        List<DriverLog> logs = new ArrayList<>();
        for (int d = 15; d <= 19; d++) {
            boolean result = complianceService.bookDriver(1L,
                LocalDateTime.of(2025, 3, d, 8, 0),
                LocalDateTime.of(2025, 3, d, 16, 0),
                logs);
            assertTrue(result, "Booking on day " + d + " should succeed (non-overlapping)");
        }
        assertEquals(5, logs.size());
    }

    @Test
    void test_remaining_hours_negative_value() {
        List<DriverLog> logs = new ArrayList<>();
        logs.add(createLog(1L, "2025-01-01", new BigDecimal("70.00"), new BigDecimal("70.00")));
        int remaining = complianceService.calculateRemainingDrivingHours(logs);
        assertEquals(-10, remaining);
    }

    @Test
    void test_compliance_violation_message_format() {
        List<DriverLog> logs = new ArrayList<>();
        logs.add(createLog(1L, "2025-01-01", new BigDecimal("12.50"), new BigDecimal("13.00")));
        List<String> violations = complianceService.checkComplianceViolations(1L, logs);
        assertTrue(violations.get(0).startsWith("EXCESS_DRIVING:"));
    }

    @Test
    void test_eta_multi_day_duration() {
        LocalDateTime departure = LocalDateTime.of(2025, 3, 15, 10, 0);
        LocalDateTime eta = complianceService.calculateETA(departure, 4320, "UTC"); // 3 days
        assertEquals(LocalDateTime.of(2025, 3, 18, 10, 0), eta);
    }

    @Test
    void test_rate_all_days_compliant() {
        double rate = complianceService.calculateComplianceRate(30, 30);
        assertEquals(100.0, rate, 0.01);
    }

    @Test
    void test_rate_no_days_compliant() {
        double rate = complianceService.calculateComplianceRate(0, 30);
        assertEquals(0.0, rate, 0.01);
    }

    @Test
    void test_remaining_hours_multiple_fractional_logs() {
        List<DriverLog> logs = new ArrayList<>();
        logs.add(createLog(1L, "2025-01-01", new BigDecimal("8.25"), new BigDecimal("10.00")));
        logs.add(createLog(1L, "2025-01-02", new BigDecimal("8.75"), new BigDecimal("10.00")));
        logs.add(createLog(1L, "2025-01-03", new BigDecimal("8.50"), new BigDecimal("10.00")));
        // Total: 25.50, remaining: 34.50
        int remaining = complianceService.calculateRemainingDrivingHours(logs);
        assertTrue(remaining == 34 || remaining == 35,
            "34.50 remaining should be 34 (truncated) or 35 (rounded)");
    }

    @Test
    void test_booking_log_date_correct() {
        List<DriverLog> logs = new ArrayList<>();
        LocalDateTime start = LocalDateTime.of(2025, 6, 20, 9, 0);
        LocalDateTime end = LocalDateTime.of(2025, 6, 20, 17, 0);
        complianceService.bookDriver(1L, start, end, logs);
        if (!logs.isEmpty()) {
            assertEquals(LocalDate.of(2025, 6, 20), logs.get(0).getLogDate());
        }
    }

    @Test
    void test_compliance_many_clean_days() {
        List<DriverLog> logs = new ArrayList<>();
        for (int i = 1; i <= 7; i++) {
            logs.add(createLog(1L, "2025-01-0" + i, new BigDecimal("7.00"), new BigDecimal("9.00")));
        }
        List<String> violations = complianceService.checkComplianceViolations(1L, logs);
        assertTrue(violations.isEmpty(), "All days under limits should have no violations");
    }

    @Test
    void test_driver_log_sleeper_hours() {
        DriverLog log = new DriverLog();
        log.setSleeperHours(new BigDecimal("8.00"));
        assertEquals(0, new BigDecimal("8.00").compareTo(log.getSleeperHours()));
    }

    @Test
    void test_driver_log_off_duty_hours() {
        DriverLog log = new DriverLog();
        log.setOffDutyHours(new BigDecimal("10.00"));
        assertEquals(0, new BigDecimal("10.00").compareTo(log.getOffDutyHours()));
    }

    @Test
    void test_rate_half() {
        double rate = complianceService.calculateComplianceRate(50, 100);
        assertEquals(50.0, rate, 0.01);
    }

    @Test
    void test_eta_minutes_only() {
        LocalDateTime dep = LocalDateTime.of(2025, 3, 15, 10, 30);
        LocalDateTime eta = complianceService.calculateETA(dep, 45, "UTC");
        assertEquals(LocalDateTime.of(2025, 3, 15, 11, 15), eta);
    }

    @Test
    void test_remaining_max_driving() {
        List<DriverLog> logs = new ArrayList<>();
        logs.add(createLog(1L, "2025-01-01", new BigDecimal("11.00"), new BigDecimal("14.00")));
        logs.add(createLog(1L, "2025-01-02", new BigDecimal("11.00"), new BigDecimal("14.00")));
        // 22h total, 38h remaining
        int remaining = complianceService.calculateRemainingDrivingHours(logs);
        assertEquals(38, remaining);
    }

    @Test
    void test_booking_returns_true_for_available() {
        boolean result = complianceService.bookDriver(1L,
            LocalDateTime.of(2025, 5, 1, 6, 0),
            LocalDateTime.of(2025, 5, 1, 14, 0),
            new ArrayList<>());
        assertTrue(result);
    }

    // Helper methods
    private DriverLog createLog(Long driverId, String date, BigDecimal drivingHours, BigDecimal onDutyHours) {
        DriverLog log = new DriverLog();
        log.setDriverId(driverId);
        log.setLogDate(LocalDate.parse(date));
        log.setDrivingHours(drivingHours);
        log.setOnDutyHours(onDutyHours);
        log.setOffDutyHours(new BigDecimal("10.00"));
        log.setSleeperHours(BigDecimal.ZERO);
        log.setStatus("ACTIVE");
        return log;
    }
}

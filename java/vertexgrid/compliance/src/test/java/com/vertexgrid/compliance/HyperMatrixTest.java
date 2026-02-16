package com.vertexgrid.compliance;

import com.vertexgrid.compliance.model.DriverLog;
import com.vertexgrid.compliance.service.ComplianceService;
import org.junit.jupiter.api.DynamicTest;
import org.junit.jupiter.api.Tag;
import org.junit.jupiter.api.TestFactory;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.time.LocalDate;
import java.util.ArrayList;
import java.util.List;
import java.util.stream.IntStream;
import java.util.stream.Stream;

import static org.junit.jupiter.api.Assertions.*;

/**
 * Stress test matrix for compliance module bugs.
 * Cycles through 3 modes testing BUGs F9, F10, and validateBreakRule.
 */
@Tag("stress")
public class HyperMatrixTest {

    private final ComplianceService complianceService = new ComplianceService();

    @TestFactory
    Stream<DynamicTest> compliance_hyper_matrix() {
        final int total = 500;
        return IntStream.range(0, total).mapToObj(idx ->
            DynamicTest.dynamicTest("compliance_hyper_" + idx, () -> {
                int mode = idx % 3;
                switch (mode) {
                    case 0 -> remainingHoursRounding_matrix(idx);
                    case 1 -> complianceRateIntDiv_matrix(idx);
                    default -> breakRuleDrivingVsOnDuty_matrix(idx);
                }
            })
        );
    }

    // BUG F9: BigDecimal.intValue() truncates instead of rounding
    private void remainingHoursRounding_matrix(int idx) {
        List<DriverLog> logs = new ArrayList<>();
        // Use driving hours with .50 or .75 fractional parts
        // where intValue() truncation differs from proper rounding
        BigDecimal[] fractionals = {
            new BigDecimal("8.50"),   // remaining=51.50 → intValue=51, HALF_UP=52
            new BigDecimal("8.25"),   // remaining=51.75 → intValue=51, HALF_UP=52
            new BigDecimal("9.50"),   // remaining=50.50 → intValue=50, HALF_UP=51
            new BigDecimal("9.75"),   // remaining=50.25 → intValue=50, HALF_UP=50 (same)
            new BigDecimal("10.50"),  // remaining=49.50 → intValue=49, HALF_UP=50
            new BigDecimal("11.50"),  // remaining=48.50 → intValue=48, HALF_UP=49
            new BigDecimal("20.50"),  // remaining=39.50 → intValue=39, HALF_UP=40
            new BigDecimal("30.50"),  // remaining=29.50 → intValue=29, HALF_UP=30
        };
        BigDecimal hours = fractionals[idx % fractionals.length];
        logs.add(createLog(1L, "2025-01-01", hours, hours.add(new BigDecimal("2.0"))));

        int remaining = complianceService.calculateRemainingDrivingHours(logs);
        BigDecimal expectedExact = new BigDecimal("60.0").subtract(hours);
        int expectedRounded = expectedExact.setScale(0, RoundingMode.HALF_UP).intValue();

        // Bug: intValue() truncates 51.50 → 51 instead of properly rounding to 52
        assertEquals(expectedRounded, remaining,
            "calculateRemainingDrivingHours with " + hours + "h driving: " +
            "remaining=" + expectedExact + ", expected rounded=" + expectedRounded +
            ", got=" + remaining + " (intValue truncation bug)");
    }

    // BUG F10: Integer division truncates compliance rate to 0
    private void complianceRateIntDiv_matrix(int idx) {
        int compliant = 1 + (idx % 99);
        int total = 100;

        double rate = complianceService.calculateComplianceRate(compliant, total);
        double expectedRate = ((double) compliant / total) * 100.0;

        if (compliant < total && compliant > 0) {
            assertTrue(rate > 0.0,
                "Compliance rate for " + compliant + "/" + total +
                " should be " + expectedRate + "%, not 0.0 (integer division bug)");
            assertEquals(expectedRate, rate, 0.01,
                "Compliance rate for " + compliant + "/" + total +
                " should be " + expectedRate + "%, got " + rate + "%");
        }
    }

    // BUG: validateBreakRule checks onDutyHours instead of drivingHours
    private void breakRuleDrivingVsOnDuty_matrix(int idx) {
        // Key scenario: high on-duty hours but low driving hours
        // FMCSA break rule applies to DRIVING hours (8h threshold)
        BigDecimal drivingHours = new BigDecimal("5.00").add(
            new BigDecimal(idx % 3).multiply(new BigDecimal("1.0"))); // 5, 6, or 7
        BigDecimal onDutyHours = new BigDecimal("9.00").add(
            new BigDecimal(idx % 5).multiply(new BigDecimal("0.5"))); // 9.0 to 11.0

        DriverLog log = createLog(1L, "2025-01-01", drivingHours, onDutyHours);
        log.setOffDutyHours(new BigDecimal("0.10")); // minimal break
        log.setSleeperHours(BigDecimal.ZERO);

        boolean result = complianceService.validateBreakRule(log);

        // Since drivingHours < 8h, the break rule should NOT apply
        // (FMCSA 30-min break is required after 8h of DRIVING, not on-duty)
        // Bug: method checks onDutyHours > 8 instead of drivingHours > 8
        // So it incorrectly requires a break even when driving hours are under 8h
        assertTrue(result,
            "With " + drivingHours + "h driving (< 8h threshold), break rule should pass. " +
            "On-duty hours (" + onDutyHours + "h) should NOT trigger the break requirement. " +
            "Bug: validateBreakRule checks onDutyHours instead of drivingHours.");
    }

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

use polariscore::statistics::{
    detect_anomalies, exponential_moving_average, percentile, rolling_sla, trimmed_mean,
};

#[test]
fn percentile_p95_returns_high_value() {
    // P95 of [10,20,30,40,50] should be >= 40.
    // Bug: complement inversion causes it to return the low end (~10).
    let result = percentile(&[10, 20, 30, 40, 50], 95);
    assert!(
        result >= 40,
        "P95 of [10..50] should be >= 40, got {}",
        result
    );
}

#[test]
fn rolling_sla_uses_full_count() {
    // 2 of 3 latencies are within objective → 0.6667
    // Bug: divides by len-1 giving 2/2 = 1.0
    let ratio = rolling_sla(&[90, 110, 160], 120);
    assert!(
        (ratio - 0.6667).abs() < 0.01,
        "SLA([90,110,160], 120) should be ~0.6667, got {}",
        ratio
    );
}

#[test]
fn trimmed_mean_divides_by_kept_count() {
    // Trim 25% from each end of [1,2,3,100] → kept = [2,3], mean = 2.5
    // Bug: divides by values.len() (4) giving 1.25
    let result = trimmed_mean(&[1.0, 2.0, 3.0, 100.0], 0.25);
    assert!(
        (result - 2.5).abs() < 0.001,
        "trimmed_mean([1,2,3,100], 0.25) should be 2.5, got {}",
        result
    );
}

#[test]
fn ema_responds_to_recent_jump() {
    // EMA([10,10,10,100], span=2) — last value should respond strongly to the jump.
    // Correct alpha = 2/3 gives last ≈ 70. Bug: alpha swap gives ≈ 40.
    let ema = exponential_moving_average(&[10.0, 10.0, 10.0, 100.0], 2);
    assert_eq!(ema.len(), 4);
    let last = ema[3];
    assert!(
        last > 50.0,
        "EMA last value after jump to 100 should be > 50, got {}",
        last
    );
}

#[test]
fn anomaly_detection_uses_sample_variance() {
    // [0,0,0,10] with sigma_threshold=1.5
    // Population variance: std ≈ 4.33, threshold = 6.495, |10-2.5|=7.5 > 6.495 → flags index 3
    // Sample variance: std = 5.0, threshold = 7.5, |10-2.5|=7.5 is NOT > 7.5 → no anomalies
    let anomalies = detect_anomalies(&[0.0, 0.0, 0.0, 10.0], 1.5);
    assert!(
        anomalies.is_empty(),
        "With sample variance, [0,0,0,10] at sigma=1.5 should have no anomalies, got {:?}",
        anomalies
    );
}

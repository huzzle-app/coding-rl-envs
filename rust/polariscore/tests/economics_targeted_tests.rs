use polariscore::economics::{break_even_units, margin_ratio, projected_cost_cents};
use polariscore::models::Shipment;

#[test]
fn surge_multiplier_scales_cost() {
    // surge=2.0 should double the base cost.
    // Bug: surge/100 adds 2% instead of multiplying by 2.0.
    let shipments = vec![Shipment {
        id: "s1".into(),
        lane: "east".into(),
        units: 10,
        priority: 3,
    }];
    let base_cost = projected_cost_cents(&shipments, 100.0, 1.0);
    let surged_cost = projected_cost_cents(&shipments, 100.0, 2.0);
    assert!(
        surged_cost >= base_cost * 18 / 10, // at least 1.8x (2.0x expected)
        "surge=2.0 should roughly double the cost; base={}, surged={}",
        base_cost,
        surged_cost
    );
}

#[test]
fn break_even_uses_subtraction() {
    // break_even(100000, 10.0, 3.0) = ceil(100000 / (10-3)) = 14286
    // Bug: uses + giving ceil(100000/13) = 7693
    let units = break_even_units(100_000, 10.0, 3.0);
    assert!(
        units > 10_000,
        "break_even should be ceil(100000/7) = 14286, got {}",
        units
    );
}

#[test]
fn margin_negative_when_cost_exceeds_revenue() {
    // margin(8000, 10000): cost exceeds revenue → margin should be negative.
    // Bug: returns 0.0 when cost > revenue.
    let m = margin_ratio(8000, 10000);
    assert!(
        m < 0.0,
        "margin_ratio(8000, 10000) should be negative, got {}",
        m
    );
}

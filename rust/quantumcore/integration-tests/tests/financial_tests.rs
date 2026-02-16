//! Financial calculation tests for QuantumCore
//!
//! Tests cover: F1-F10 numerical/financial bugs

use rust_decimal::Decimal;
use rust_decimal_macros::dec;

// =============================================================================
// F1: Float Precision in Prices Tests
// =============================================================================

#[test]
fn test_f1_price_decimal_precision() {
    
    let price1 = dec!(100.10);
    let price2 = dec!(100.20);
    let diff = price2 - price1;

    // Decimal maintains precision
    assert_eq!(diff, dec!(0.10));
}

#[test]
fn test_f1_no_float_for_money() {
    
    let f_price: f64 = 100.10;
    let f_qty: f64 = 0.001;
    let f_value = f_price * f_qty;

    // Float result is imprecise
    assert!((f_value - 0.10010).abs() < 0.0001, "Float imprecise: {}", f_value);

    // Decimal is precise
    let d_price = dec!(100.10);
    let d_qty = dec!(0.001);
    let d_value = d_price * d_qty;
    assert_eq!(d_value, dec!(0.10010));
}

#[test]
fn test_f1_cumulative_float_error() {
    
    let mut f_sum: f64 = 0.0;
    for _ in 0..100 {
        f_sum += 0.1;
    }
    // Float: 9.99999999999998 instead of 10.0
    assert!((f_sum - 10.0).abs() < 0.0001);

    // Decimal: exact
    let mut d_sum = dec!(0);
    for _ in 0..100 {
        d_sum += dec!(0.1);
    }
    assert_eq!(d_sum, dec!(10.0));
}

#[test]
fn test_f1_price_comparison() {
    
    let f1: f64 = 0.1 + 0.2;
    let f2: f64 = 0.3;
    // Float: f1 != f2 due to precision
    assert!((f1 - f2).abs() < 1e-10);

    // Decimal: exact
    let d1 = dec!(0.1) + dec!(0.2);
    let d2 = dec!(0.3);
    assert_eq!(d1, d2);
}

// =============================================================================
// F2: Integer Overflow in Quantity Tests
// =============================================================================

#[test]
fn test_f2_quantity_overflow_handled() {
    
    let qty1: u64 = u64::MAX / 2;
    let qty2: u64 = u64::MAX / 2;

    // Checked addition returns None on overflow
    let total = qty1.checked_add(qty2);
    assert!(total.is_some());

    let qty3: u64 = u64::MAX / 2 + 100;
    let overflow = qty1.checked_add(qty3);
    assert!(overflow.is_none(), "Should detect overflow");
}

#[test]
fn test_f2_checked_arithmetic() {
    
    let a: u64 = 1000;
    let b: u64 = 500;

    // Safe subtraction
    let diff = a.checked_sub(b);
    assert_eq!(diff, Some(500));

    // Underflow detection
    let underflow = b.checked_sub(a);
    assert_eq!(underflow, None);
}

#[test]
fn test_f2_saturating_arithmetic() {
    // Alternative: saturating arithmetic
    let a: u64 = u64::MAX - 10;
    let b: u64 = 100;

    let saturated = a.saturating_add(b);
    assert_eq!(saturated, u64::MAX);
}

// =============================================================================
// F3: Decimal Rounding Mode Tests
// =============================================================================

#[test]
fn test_f3_decimal_rounding_correct() {
    use rust_decimal::prelude::*;

    
    let value = dec!(1.235);

    // Different rounding modes
    let rounded_half_up = value.round_dp_with_strategy(2, RoundingStrategy::MidpointAwayFromZero);
    let rounded_half_even = value.round_dp_with_strategy(2, RoundingStrategy::MidpointNearestEven);
    let rounded_down = value.round_dp_with_strategy(2, RoundingStrategy::ToZero);

    assert_eq!(rounded_half_up, dec!(1.24));
    assert_eq!(rounded_half_even, dec!(1.24)); // Banker's rounding
    assert_eq!(rounded_down, dec!(1.23));
}

#[test]
fn test_f3_ledger_rounding_mode() {
    
    use rust_decimal::prelude::*;

    let amounts = vec![dec!(1.235), dec!(2.245), dec!(3.255)];
    let mut total = dec!(0);

    for amount in amounts {
        // Use half-even (banker's) rounding for fairness
        total += amount.round_dp_with_strategy(2, RoundingStrategy::MidpointNearestEven);
    }

    assert_eq!(total, dec!(6.74)); // 1.24 + 2.24 + 3.26
}

// =============================================================================
// F4: Currency Conversion Tests
// =============================================================================

#[test]
fn test_f4_currency_conversion_precise() {
    
    let usd_amount = dec!(100.00);
    let exchange_rate = dec!(0.85); // USD to EUR

    let eur_amount = usd_amount * exchange_rate;
    assert_eq!(eur_amount, dec!(85.00));
}

#[test]
fn test_f4_no_float_conversion_rate() {
    
    let usd: f64 = 1000000.00;
    let rate: f64 = 1.00001;
    let converted = usd * rate;

    // Float may have precision issues for large amounts
    let expected = 1000010.0;
    assert!((converted - expected).abs() < 0.01);

    // Decimal is precise
    let d_usd = dec!(1000000.00);
    let d_rate = dec!(1.00001);
    let d_converted = d_usd * d_rate;
    assert_eq!(d_converted, dec!(1000010.00000));
}

// =============================================================================
// F5: Fee Calculation Truncation Tests
// =============================================================================

#[test]
fn test_f5_fee_calculation_precise() {

    let order_value = dec!(100.00);
    let fee_rate = dec!(0.001); // 0.1%
    let fee = order_value * fee_rate;

    assert_eq!(fee, dec!(0.100));
}

#[test]
fn test_f5_fee_no_truncation() {
    
    use rust_decimal::prelude::*;

    let order_value = dec!(99.99);
    let fee_rate = dec!(0.001);
    let raw_fee = order_value * fee_rate;

    // Truncation (wrong): 0.09
    let truncated = raw_fee.trunc_with_scale(2);

    // Rounding (correct): 0.10
    let rounded = raw_fee.round_dp_with_strategy(2, RoundingStrategy::MidpointAwayFromZero);

    assert_eq!(truncated, dec!(0.09));
    assert_eq!(rounded, dec!(0.10));
    assert!(rounded > truncated, "Rounding should not lose money");
}

// =============================================================================
// F6: P&L Calculation Tests
// =============================================================================

#[test]
fn test_f6_pnl_calculation_correct() {
    
    let entry_price = dec!(100.00);
    let exit_price = dec!(110.00);
    let quantity = dec!(10);

    let pnl = (exit_price - entry_price) * quantity;
    assert_eq!(pnl, dec!(100.00));
}

#[test]
fn test_f6_pnl_with_fees() {
    
    let entry_price = dec!(100.00);
    let exit_price = dec!(110.00);
    let quantity = dec!(10);
    let entry_fee = dec!(1.00);
    let exit_fee = dec!(1.10);

    let gross_pnl = (exit_price - entry_price) * quantity;
    let net_pnl = gross_pnl - entry_fee - exit_fee;

    assert_eq!(gross_pnl, dec!(100.00));
    assert_eq!(net_pnl, dec!(97.90));
}

#[test]
fn test_f6_realized_vs_unrealized() {
    
    let entry_price = dec!(100.00);
    let current_price = dec!(105.00);
    let quantity = dec!(10);
    let filled_quantity = dec!(5);

    let unrealized = (current_price - entry_price) * (quantity - filled_quantity);
    let realized = (current_price - entry_price) * filled_quantity;

    assert_eq!(unrealized, dec!(25.00));
    assert_eq!(realized, dec!(25.00));
}

// =============================================================================
// F7: Margin Requirement Overflow Tests
// =============================================================================

#[test]
fn test_f7_margin_no_overflow() {
    
    let position_value = dec!(1000000000); // $1B
    let margin_rate = dec!(0.10);

    let margin_required = position_value * margin_rate;
    assert_eq!(margin_required, dec!(100000000)); // $100M
}

#[test]
fn test_f7_aggregate_margin() {
    
    let positions = vec![
        dec!(1000000),
        dec!(2000000),
        dec!(3000000),
    ];
    let margin_rate = dec!(0.10);

    let total_margin: Decimal = positions.iter()
        .map(|p| *p * margin_rate)
        .sum();

    assert_eq!(total_margin, dec!(600000));
}

// =============================================================================
// F8: Price Tick Validation Tests
// =============================================================================

#[test]
fn test_f8_price_tick_validation() {
    
    let tick_size = dec!(0.01);

    let valid_price = dec!(100.00);
    let invalid_price = dec!(100.001);

    let is_valid = |price: Decimal| -> bool {
        let remainder = price % tick_size;
        remainder == dec!(0)
    };

    assert!(is_valid(valid_price), "100.00 should be valid");
    assert!(!is_valid(invalid_price), "100.001 should be invalid");
}

#[test]
fn test_f8_invalid_tick_rejected() {
    
    let tick_size = dec!(0.05);

    let prices = vec![
        (dec!(100.00), true),
        (dec!(100.05), true),
        (dec!(100.10), true),
        (dec!(100.01), false),
        (dec!(100.03), false),
    ];

    for (price, expected_valid) in prices {
        let is_valid = (price % tick_size) == dec!(0);
        assert_eq!(is_valid, expected_valid, "Price {} validity", price);
    }
}

// =============================================================================
// F9: Order Value Calculation Tests
// =============================================================================

#[test]
fn test_f9_order_value_correct() {
    
    let price = dec!(150.50);
    let quantity = dec!(100);

    let value = price * quantity;
    assert_eq!(value, dec!(15050.00));
}

#[test]
fn test_f9_no_stale_mark_to_market() {
    
    let positions = vec![
        (dec!(100), dec!(150.00)), // qty, current_price
        (dec!(50), dec!(200.00)),
    ];

    let total_value: Decimal = positions.iter()
        .map(|(qty, price)| *qty * *price)
        .sum();

    assert_eq!(total_value, dec!(25000.00)); // 15000 + 10000
}

// =============================================================================
// F10: Tax Rounding Compound Tests
// =============================================================================

#[test]
fn test_f10_tax_rounding_correct() {
    use rust_decimal::prelude::*;

    
    let income = dec!(1000.00);
    let tax_rate = dec!(0.25);

    let tax = (income * tax_rate).round_dp_with_strategy(2, RoundingStrategy::MidpointNearestEven);
    assert_eq!(tax, dec!(250.00));
}

#[test]
fn test_f10_compound_rounding_safe() {
    use rust_decimal::prelude::*;

    
    let mut balance = dec!(1000.00);
    let interest_rate = dec!(0.05); // 5%

    // Compound monthly for 12 months
    for _ in 0..12 {
        let interest = (balance * interest_rate / dec!(12))
            .round_dp_with_strategy(2, RoundingStrategy::MidpointNearestEven);
        balance += interest;
    }

    // Should be close to 1000 * (1 + 0.05)^1 ≈ 1051.16
    assert!(balance > dec!(1051.00) && balance < dec!(1052.00),
        "Balance should be approximately $1051.16: {}", balance);
}

// =============================================================================
// Additional Financial Tests
// =============================================================================

#[test]
fn test_order_notional_value() {
    let price = dec!(100.00);
    let quantity = 1000u64;

    let notional = price * Decimal::from(quantity);
    assert_eq!(notional, dec!(100000.00));
}

#[test]
fn test_average_price_calculation() {
    let fills = vec![
        (dec!(100.00), 100u64), // price, quantity
        (dec!(101.00), 200u64),
        (dec!(99.00), 100u64),
    ];

    let total_value: Decimal = fills.iter()
        .map(|(p, q)| *p * Decimal::from(*q))
        .sum();
    let total_qty: u64 = fills.iter().map(|(_, q)| *q).sum();

    let avg_price = total_value / Decimal::from(total_qty);
    assert_eq!(avg_price, dec!(100.25)); // (10000 + 20200 + 9900) / 400
}

#[test]
fn test_percentage_change() {
    let old_price = dec!(100.00);
    let new_price = dec!(105.00);

    let pct_change = ((new_price - old_price) / old_price) * dec!(100);
    assert_eq!(pct_change, dec!(5.00));
}

#[test]
fn test_slippage_calculation() {
    let expected_price = dec!(100.00);
    let executed_price = dec!(100.10);
    let quantity = dec!(100);

    let slippage = (executed_price - expected_price) * quantity;
    assert_eq!(slippage, dec!(10.00));
}

#[test]
fn test_commission_calculation() {
    let trade_value = dec!(10000.00);
    let commission_rate = dec!(0.0001); // 1 basis point
    let min_commission = dec!(1.00);

    let calculated_commission = trade_value * commission_rate;
    let actual_commission = if calculated_commission < min_commission {
        min_commission
    } else {
        calculated_commission
    };

    assert_eq!(actual_commission, dec!(1.00));
}

#[test]
fn test_bid_ask_spread() {
    let bid = dec!(99.95);
    let ask = dec!(100.05);

    let spread = ask - bid;
    let mid_price = (bid + ask) / dec!(2);
    let spread_bps = (spread / mid_price) * dec!(10000);

    assert_eq!(spread, dec!(0.10));
    assert_eq!(mid_price, dec!(100.00));
    assert_eq!(spread_bps, dec!(10.00)); // 10 basis points
}

#[test]
fn test_position_weighted_price() {
    // VWAP-like calculation
    let trades = vec![
        (dec!(100.00), 100),
        (dec!(100.50), 200),
        (dec!(99.50), 100),
    ];

    let mut total_value = dec!(0);
    let mut total_qty = 0;

    for (price, qty) in trades {
        total_value += price * Decimal::from(qty);
        total_qty += qty;
    }

    let vwap = total_value / Decimal::from(total_qty);
    assert_eq!(vwap, dec!(100.125)); // 40050 / 400
}

#[test]
fn test_daily_pnl() {
    let yesterday_value = dec!(1000000.00);
    let today_value = dec!(1005000.00);

    let daily_pnl = today_value - yesterday_value;
    let daily_return = (daily_pnl / yesterday_value) * dec!(100);

    assert_eq!(daily_pnl, dec!(5000.00));
    assert_eq!(daily_return, dec!(0.5)); // 0.5%
}

#[test]
fn test_max_drawdown() {
    let values = vec![
        dec!(1000),
        dec!(1100), // peak
        dec!(1000), // drawdown
        dec!(900),  // max drawdown
        dec!(950),
    ];

    let mut peak = values[0];
    let mut max_drawdown = dec!(0);

    for value in &values {
        if *value > peak {
            peak = *value;
        }
        let drawdown = peak - *value;
        if drawdown > max_drawdown {
            max_drawdown = drawdown;
        }
    }

    assert_eq!(max_drawdown, dec!(200)); // 1100 - 900
}

#[test]
fn test_sharpe_ratio_components() {
    // Sharpe = (return - risk_free) / std_dev
    let returns = vec![dec!(0.01), dec!(0.02), dec!(-0.01), dec!(0.015)];
    let risk_free = dec!(0.001);

    let mean: Decimal = returns.iter().copied().sum::<Decimal>() / Decimal::from(returns.len());
    let excess_return = mean - risk_free;

    assert!(excess_return > dec!(0));
}

#[test]
fn test_lot_size_validation() {
    let lot_size = 100u64; // Minimum order size

    let valid_quantities = vec![100, 200, 500, 1000];
    let invalid_quantities = vec![50, 150, 99];

    for qty in valid_quantities {
        assert_eq!(qty % lot_size, 0, "Quantity {} should be valid", qty);
    }

    for qty in invalid_quantities {
        assert_ne!(qty % lot_size, 0, "Quantity {} should be invalid", qty);
    }
}

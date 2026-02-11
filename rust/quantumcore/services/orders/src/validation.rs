//! Order validation
//!
//! BUG F1: Float precision in prices
//! BUG F5: Fee calculation truncation
//! BUG F9: Order value calculation wrong

use anyhow::{anyhow, Result};
use rust_decimal::Decimal;
use std::str::FromStr;

#[derive(Debug, Clone)]
pub struct OrderRequest {
    pub symbol: String,
    pub side: String,
    pub quantity: f64,  
    pub price: f64,     
}

#[derive(Debug, Clone)]
pub struct ValidatedOrder {
    pub symbol: String,
    pub side: String,
    pub quantity: Decimal,
    pub price: Decimal,
    pub value: Decimal,
    pub fee: Decimal,
}

const FEE_RATE: f64 = 0.001;  // 0.1% fee

/// Validate and prepare order
/
pub fn validate_order(request: &OrderRequest) -> Result<ValidatedOrder> {
    // Validate symbol
    if request.symbol.is_empty() {
        return Err(anyhow!("Symbol is required"));
    }

    // Validate side
    if request.side != "buy" && request.side != "sell" {
        return Err(anyhow!("Side must be 'buy' or 'sell'"));
    }

    // Validate quantity
    if request.quantity <= 0.0 {
        return Err(anyhow!("Quantity must be positive"));
    }

    // Validate price
    if request.price <= 0.0 {
        return Err(anyhow!("Price must be positive"));
    }

    
    // Should use Decimal from the start
    let quantity = Decimal::from_str(&format!("{:.8}", request.quantity))
        .map_err(|e| anyhow!("Invalid quantity: {}", e))?;

    let price = Decimal::from_str(&format!("{:.8}", request.price))
        .map_err(|e| anyhow!("Invalid price: {}", e))?;

    
    let value_f64 = request.quantity * request.price;
    let value = Decimal::from_str(&format!("{:.8}", value_f64))
        .map_err(|e| anyhow!("Invalid value: {}", e))?;

    
    let fee = calculate_fee(value_f64);

    Ok(ValidatedOrder {
        symbol: request.symbol.clone(),
        side: request.side.clone(),
        quantity,
        price,
        value,
        fee,
    })
}

/// Calculate trading fee
/
fn calculate_fee(value: f64) -> Decimal {
    let fee_f64 = value * FEE_RATE;

    
    let truncated = (fee_f64 * 100.0).floor() / 100.0;

    Decimal::from_str(&format!("{:.2}", truncated)).unwrap_or_default()
}

/// Validate order quantity against position limits
pub fn validate_quantity_limit(quantity: Decimal, max_position: Decimal) -> Result<()> {
    if quantity > max_position {
        return Err(anyhow!("Quantity {} exceeds maximum position {}", quantity, max_position));
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_float_precision_loss() {
        
        let request = OrderRequest {
            symbol: "BTC/USD".to_string(),
            side: "buy".to_string(),
            quantity: 0.1 + 0.2,  // Famous float issue: != 0.3
            price: 50000.01,
        };

        let validated = validate_order(&request).unwrap();

        // This assertion may fail due to float precision
        // The bug is that we use f64 at all
        assert!(validated.quantity > Decimal::ZERO);
    }

    #[test]
    fn test_fee_truncation() {
        
        let fee = calculate_fee(149.99);

        // Expected: 0.15 (149.99 * 0.001 = 0.14999, rounds to 0.15)
        // Actual: 0.14 (truncated)
        assert_eq!(fee, Decimal::from_str("0.14").unwrap());
    }

    #[test]
    fn test_order_value_calculation() {
        
        let request = OrderRequest {
            symbol: "BTC/USD".to_string(),
            side: "buy".to_string(),
            quantity: 0.001,
            price: 50000.0,
        };

        let validated = validate_order(&request).unwrap();

        // Should be exactly 50.0, but float math may differ
        let expected = Decimal::from_str("50.0").unwrap();
        assert_eq!(validated.value, expected);
    }
}

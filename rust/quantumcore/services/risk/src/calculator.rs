use anyhow::Result;
use dashmap::DashMap;
use parking_lot::RwLock;
use rust_decimal::Decimal;
use rust_decimal_macros::dec;
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::sync::Arc;
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Position {
    pub account_id: String,
    pub symbol: String,
    pub quantity: i64,  // Positive for long, negative for short
    pub average_price: Decimal,
    pub unrealized_pnl: Decimal,
    pub realized_pnl: Decimal,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RiskMetrics {
    pub account_id: String,
    pub total_exposure: Decimal,
    pub margin_used: Decimal,
    pub margin_available: Decimal,
    pub var_95: Decimal,  // Value at Risk 95%
    pub var_99: Decimal,  // Value at Risk 99%
    pub max_drawdown: Decimal,
}

pub struct RiskCalculator {
    positions: DashMap<String, HashMap<String, Position>>,  // account_id -> symbol -> position
    market_prices: DashMap<String, Decimal>,
    
    risk_cache: DashMap<String, RiskMetrics>,
    
    volatilities: DashMap<String, f64>,
    correlations: Arc<RwLock<HashMap<(String, String), f64>>>,
}

impl RiskCalculator {
    pub fn new() -> Self {
        Self {
            positions: DashMap::new(),
            market_prices: DashMap::new(),
            risk_cache: DashMap::new(),
            volatilities: DashMap::new(),
            correlations: Arc::new(RwLock::new(HashMap::new())),
        }
    }

    
    pub fn calculate_margin_requirement(&self, account_id: &str) -> Result<Decimal> {
        let positions = self.positions.get(account_id)
            .ok_or_else(|| anyhow::anyhow!("Account not found"))?;

        let mut total_margin = 0.0_f64;  

        for (symbol, position) in positions.iter() {
            let price = self.market_prices.get(symbol)
                .map(|p| *p)
                .unwrap_or(position.average_price);

            
            let position_value = position.quantity.abs() as f64 * price.to_string().parse::<f64>().unwrap_or(0.0);

            
            let volatility = self.volatilities.get(symbol)
                .map(|v| *v)
                .unwrap_or(0.02);  // Default 2% volatility

            // Margin = position_value * volatility * multiplier
            let margin = position_value * volatility * 2.5;
            total_margin += margin;
        }

        
        Ok(Decimal::from_f64_retain(total_margin).unwrap_or(Decimal::ZERO))
    }

    pub fn check_order_risk(&self, account_id: &str, symbol: &str, quantity: i64, price: Decimal) -> Result<bool> {
        
        let current_margin = self.calculate_margin_requirement(account_id)?;
        let account_limit = self.get_account_limit(account_id)?;
        let margin_available = account_limit - current_margin;

        
        // This is a TOCTOU (time-of-check-time-of-use) bug

        // Calculate additional margin required
        let volatility = self.volatilities.get(symbol)
            .map(|v| *v)
            .unwrap_or(0.02);

        
        let order_value = quantity.abs() as f64 * price.to_string().parse::<f64>().unwrap_or(0.0);
        let additional_margin = Decimal::from_f64_retain(order_value * volatility * 2.5)
            .unwrap_or(Decimal::ZERO);

        Ok(margin_available >= additional_margin)
    }

    
    pub fn calculate_var(&self, account_id: &str, confidence: f64) -> Result<Decimal> {
        let positions = self.positions.get(account_id)
            .ok_or_else(|| anyhow::anyhow!("Account not found"))?;

        let correlations = self.correlations.read();

        
        let mut portfolio_variance = 0.0_f64;

        let symbols: Vec<_> = positions.keys().cloned().collect();

        for (i, symbol1) in symbols.iter().enumerate() {
            let pos1 = &positions[symbol1];
            let price1 = self.market_prices.get(symbol1)
                .map(|p| p.to_string().parse::<f64>().unwrap_or(0.0))
                .unwrap_or(0.0);
            let value1 = pos1.quantity.abs() as f64 * price1;
            let vol1 = self.volatilities.get(symbol1).map(|v| *v).unwrap_or(0.02);

            for (j, symbol2) in symbols.iter().enumerate() {
                let pos2 = &positions[symbol2];
                let price2 = self.market_prices.get(symbol2)
                    .map(|p| p.to_string().parse::<f64>().unwrap_or(0.0))
                    .unwrap_or(0.0);
                let value2 = pos2.quantity.abs() as f64 * price2;
                let vol2 = self.volatilities.get(symbol2).map(|v| *v).unwrap_or(0.02);

                let correlation = if i == j {
                    1.0
                } else {
                    let key = if symbol1 < symbol2 {
                        (symbol1.clone(), symbol2.clone())
                    } else {
                        (symbol2.clone(), symbol1.clone())
                    };
                    *correlations.get(&key).unwrap_or(&0.5)
                };

                
                portfolio_variance += value1 * value2 * vol1 * vol2 * correlation;
            }
        }

        
        let portfolio_std = portfolio_variance.sqrt();

        // Z-score for confidence level (approximation)
        let z_score = if confidence >= 0.99 {
            2.326
        } else if confidence >= 0.95 {
            1.645
        } else {
            1.0
        };

        let var = portfolio_std * z_score;

        
        Ok(Decimal::from_f64_retain(var).unwrap_or(Decimal::ZERO))
    }

    
    pub fn update_position(&self, account_id: &str, symbol: &str, quantity_delta: i64, price: Decimal) -> Result<Position> {
        let mut account_positions = self.positions.entry(account_id.to_string())
            .or_insert_with(HashMap::new);

        let position = account_positions.entry(symbol.to_string()).or_insert(Position {
            account_id: account_id.to_string(),
            symbol: symbol.to_string(),
            quantity: 0,
            average_price: Decimal::ZERO,
            unrealized_pnl: Decimal::ZERO,
            realized_pnl: Decimal::ZERO,
        });

        
        let old_quantity = position.quantity;
        let new_quantity = position.quantity + quantity_delta;

        // Update average price (weighted average)
        if (old_quantity >= 0 && quantity_delta > 0) || (old_quantity <= 0 && quantity_delta < 0) {
            // Adding to position - calculate new average
            let old_value = position.average_price * Decimal::from(old_quantity.abs());
            let new_value = price * Decimal::from(quantity_delta.abs());

            
            let total_value = old_value + new_value;
            position.average_price = total_value / Decimal::from(new_quantity.abs());
        }
        // Reducing position - average price stays same, calculate realized P&L
        else {
            let close_quantity = quantity_delta.abs().min(old_quantity.abs());
            let pnl_per_unit = if old_quantity > 0 {
                price - position.average_price
            } else {
                position.average_price - price
            };
            position.realized_pnl += pnl_per_unit * Decimal::from(close_quantity);
        }

        position.quantity = new_quantity;

        
        // Stale risk metrics will be served until next recalculation

        Ok(position.clone())
    }

    fn get_account_limit(&self, _account_id: &str) -> Result<Decimal> {
        
        Ok(dec!(1_000_000))
    }

    pub fn update_market_price(&self, symbol: &str, price: Decimal) {
        self.market_prices.insert(symbol.to_string(), price);
        
    }

    pub fn update_volatility(&self, symbol: &str, volatility: f64) {
        self.volatilities.insert(symbol.to_string(), volatility);
    }
}

// Correct implementation for F1/F3 (precision):
// Use rust_decimal for ALL financial calculations:
//
// pub fn calculate_margin_requirement(&self, account_id: &str) -> Result<Decimal> {
//     let mut total_margin = Decimal::ZERO;
//
//     for (symbol, position) in positions.iter() {
//         let price = self.market_prices.get(symbol).map(|p| *p).unwrap_or(position.average_price);
//         let position_value = price * Decimal::from(position.quantity.abs());
//         let volatility = self.volatilities_decimal.get(symbol).map(|v| *v).unwrap_or(dec!(0.02));
//         let margin = position_value * volatility * dec!(2.5);
//         total_margin += margin;
//     }
//
//     Ok(total_margin)
// }

// Correct implementation for G1 (race condition):
// Use optimistic locking or distributed transactions:
//
// pub fn check_and_reserve_margin(&self, account_id: &str, required_margin: Decimal) -> Result<MarginReservation> {
//     let mut account = self.accounts.write(account_id)?;
//
//     if account.margin_available < required_margin {
//         return Err(anyhow::anyhow!("Insufficient margin"));
//     }
//
//     account.margin_reserved += required_margin;
//     account.margin_available -= required_margin;
//
//     Ok(MarginReservation {
//         id: Uuid::new_v4(),
//         amount: required_margin,
//     })
// }

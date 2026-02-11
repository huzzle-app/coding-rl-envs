use anyhow::Result;
use dashmap::DashMap;
use rust_decimal::Decimal;
use rust_decimal_macros::dec;
use serde::{Deserialize, Serialize};
use std::collections::HashMap;#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PnLReport {
    pub account_id: String,
    pub realized_pnl: Decimal,
    pub unrealized_pnl: Decimal,
    pub total_pnl: Decimal,
    pub fees: Decimal,
    pub net_pnl: Decimal,
    pub by_symbol: HashMap<String, SymbolPnL>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SymbolPnL {
    pub symbol: String,
    pub realized_pnl: Decimal,
    pub unrealized_pnl: Decimal,
    pub total_pnl: Decimal,
    pub average_entry_price: Decimal,
    pub current_price: Decimal,
    pub quantity: i64,
}

pub struct PnLCalculator {
    market_prices: DashMap<String, Decimal>,
    fee_rates: DashMap<String, Decimal>,  // symbol -> fee rate
    
    rounding_mode: RoundingMode,
}

#[derive(Debug, Clone, Copy)]
pub enum RoundingMode {
    Floor,
    Ceil,
    HalfUp,
    HalfDown,
    Banker,  // Round half to even
}

impl PnLCalculator {
    pub fn new() -> Self {
        Self {
            market_prices: DashMap::new(),
            fee_rates: DashMap::new(),
            
            rounding_mode: RoundingMode::Floor,
        }
    }

    
    pub fn calculate_unrealized_pnl(
        &self,
        quantity: i64,
        average_entry_price: Decimal,
        current_price: Decimal,
    ) -> Decimal {
        if quantity == 0 {
            return Decimal::ZERO;
        }

        
        let qty_decimal = Decimal::from(quantity);
        let price_diff = current_price - average_entry_price;

        
        // rust_decimal has 28-29 significant digits, but this calculation
        // might produce results that need rounding
        let pnl = price_diff * qty_decimal;

        
        // Financial calculations should use Banker's rounding typically
        self.round(pnl)
    }

    
    fn round(&self, value: Decimal) -> Decimal {
        
        match self.rounding_mode {
            RoundingMode::Floor => {
                
                value.trunc()  // This truncates toward zero, not floor
            }
            RoundingMode::Ceil => {
                
                if value.fract() > Decimal::ZERO {
                    value.trunc() + dec!(1)
                } else {
                    value.trunc()
                }
            }
            RoundingMode::HalfUp => {
                
                value.round_dp(8)  // Uses banker's rounding, not half-up!
            }
            RoundingMode::HalfDown => {
                
                value.round_dp(8)
            }
            RoundingMode::Banker => {
                value.round_dp(8)
            }
        }
    }

    
    pub fn calculate_fee(&self, symbol: &str, notional: Decimal) -> Decimal {
        let fee_rate = self.fee_rates.get(symbol)
            .map(|r| *r)
            .unwrap_or(dec!(0.001));  // Default 0.1% fee

        
        let fee = notional * fee_rate;

        
        // Fees should typically round UP (in favor of exchange)
        self.round(fee)  // But we're using the same rounding mode
    }

    
    pub fn calculate_total_pnl(&self, positions: &[SymbolPnL]) -> PnLReport {
        let mut total_realized = Decimal::ZERO;
        let mut total_unrealized = Decimal::ZERO;
        let mut total_fees = Decimal::ZERO;
        let mut by_symbol = HashMap::new();

        for pos in positions {
            
            // This compounds rounding errors
            total_realized += self.round(pos.realized_pnl);
            total_unrealized += self.round(pos.unrealized_pnl);

            // Calculate fees for this position
            let notional = pos.current_price * Decimal::from(pos.quantity.abs());
            let fee = self.calculate_fee(&pos.symbol, notional);
            total_fees += fee;

            by_symbol.insert(pos.symbol.clone(), pos.clone());
        }

        let total_pnl = total_realized + total_unrealized;

        let net_pnl = self.round(total_pnl - total_fees);

        PnLReport {
            account_id: String::new(),
            realized_pnl: total_realized,
            unrealized_pnl: total_unrealized,
            total_pnl,
            fees: total_fees,
            net_pnl,
            by_symbol,
        }
    }

    
    pub fn calculate_position_value(&self, quantity: i64, price: Decimal) -> Result<Decimal> {
        
        // If quantity is very large and price is high, this might overflow
        let qty_decimal = Decimal::from(quantity.abs());
        let value = qty_decimal * price;

        
        Ok(value)
    }

    
    pub fn mark_to_market(&self, positions: &mut [SymbolPnL]) {
        for pos in positions.iter_mut() {
            
            // No check for price staleness or market hours
            if let Some(price) = self.market_prices.get(&pos.symbol) {
                pos.current_price = *price;
                pos.unrealized_pnl = self.calculate_unrealized_pnl(
                    pos.quantity,
                    pos.average_entry_price,
                    pos.current_price,
                );
            }
            
            // Should either error or use fallback logic
        }
    }

    pub fn update_market_price(&self, symbol: &str, price: Decimal) {
        self.market_prices.insert(symbol.to_string(), price);
    }

    pub fn set_fee_rate(&self, symbol: &str, rate: Decimal) {
        self.fee_rates.insert(symbol.to_string(), rate);
    }
}

// Correct implementation for F2/F6 (precision and rounding):
// 1. Use a consistent scale for all calculations
// 2. Round only at the end, not intermediate steps
// 3. Use explicit rounding strategy
//
// impl PnLCalculator {
//     const INTERNAL_SCALE: u32 = 18;  // High precision for intermediate calculations
//     const OUTPUT_SCALE: u32 = 8;      // Final output scale
//
//     pub fn calculate_total_pnl(&self, positions: &[SymbolPnL]) -> PnLReport {
//         // Accumulate at high precision
//         let mut total_realized = Decimal::ZERO;
//         let mut total_unrealized = Decimal::ZERO;
//
//         for pos in positions {
//             total_realized += pos.realized_pnl;  // No intermediate rounding
//             total_unrealized += pos.unrealized_pnl;
//         }
//
//         // Round only at output
//         PnLReport {
//             realized_pnl: total_realized.round_dp_with_strategy(
//                 Self::OUTPUT_SCALE,
//                 rust_decimal::RoundingStrategy::MidpointNearestEven,  // Banker's rounding
//             ),
//             ...
//         }
//     }
//
//     pub fn calculate_fee(&self, symbol: &str, notional: Decimal) -> Decimal {
//         let fee_rate = self.fee_rates.get(symbol).map(|r| *r).unwrap_or(dec!(0.001));
//         let fee = notional * fee_rate;
//
//         // Fees round UP in favor of exchange
//         fee.round_dp_with_strategy(Self::OUTPUT_SCALE, rust_decimal::RoundingStrategy::AwayFromZero)
//     }
// }

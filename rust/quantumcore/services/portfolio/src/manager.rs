use anyhow::Result;
use chrono::{DateTime, Utc};
use dashmap::DashMap;
use parking_lot::RwLock;
use rust_decimal::Decimal;
use rust_decimal_macros::dec;
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::sync::Arc;




#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Portfolio {
    pub account_id: String,
    pub positions: HashMap<String, PortfolioPosition>,
    pub cash_balance: Decimal,
    pub total_value: Decimal,
    pub last_updated: DateTime<Utc>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PortfolioPosition {
    pub symbol: String,
    pub quantity: i64,
    pub average_cost: Decimal,
    pub current_price: Decimal,
    pub market_value: Decimal,
    pub unrealized_pnl: Decimal,
    pub unrealized_pnl_percent: Decimal,
}

pub struct PortfolioManager {
    portfolios: DashMap<String, Portfolio>,
    
    valuation_cache: DashMap<String, (Portfolio, DateTime<Utc>)>,
    cache_ttl_seconds: i64,
    
    metrics: Arc<RwLock<HashMap<String, HashMap<String, PositionMetrics>>>>,
    market_prices: DashMap<String, Decimal>,
}

#[derive(Debug, Clone, Default)]
struct PositionMetrics {
    valuation_count: u64,
    last_valuation_time: Option<DateTime<Utc>>,
    cache_hits: u64,
    cache_misses: u64,
}

impl PortfolioManager {
    pub fn new(cache_ttl_seconds: i64) -> Self {
        Self {
            portfolios: DashMap::new(),
            valuation_cache: DashMap::new(),
            cache_ttl_seconds,
            metrics: Arc::new(RwLock::new(HashMap::new())),
            market_prices: DashMap::new(),
        }
    }

    
    pub fn get_portfolio(&self, account_id: &str) -> Result<Portfolio> {
        let now = Utc::now();

        // Check cache
        if let Some(cached) = self.valuation_cache.get(account_id) {
            let (portfolio, cached_at) = cached.value();
            let age = (now - *cached_at).num_seconds();

            
            self.record_metric(account_id, true);

            if age < self.cache_ttl_seconds {
                return Ok(portfolio.clone());
            }
        }

        
        // No singleflight/coalescing pattern
        self.record_metric(account_id, false);

        // Calculate portfolio value
        let portfolio = self.calculate_portfolio(account_id)?;

        
        self.valuation_cache.insert(account_id.to_string(), (portfolio.clone(), now));

        Ok(portfolio)
    }

    fn calculate_portfolio(&self, account_id: &str) -> Result<Portfolio> {
        let base_portfolio = self.portfolios.get(account_id)
            .ok_or_else(|| anyhow::anyhow!("Portfolio not found"))?;

        let mut positions = HashMap::new();
        let mut total_value = base_portfolio.cash_balance;

        for (symbol, pos) in &base_portfolio.positions {
            let current_price = self.market_prices.get(symbol)
                .map(|p| *p)
                .unwrap_or(pos.current_price);

            let market_value = current_price * Decimal::from(pos.quantity.abs());
            let cost_basis = pos.average_cost * Decimal::from(pos.quantity.abs());
            let unrealized_pnl = if pos.quantity > 0 {
                market_value - cost_basis
            } else {
                cost_basis - market_value
            };

            let unrealized_pnl_percent = if cost_basis != Decimal::ZERO {
                (unrealized_pnl / cost_basis) * dec!(100)
            } else {
                Decimal::ZERO
            };

            
            self.record_position_metric(account_id, symbol);

            positions.insert(symbol.clone(), PortfolioPosition {
                symbol: symbol.clone(),
                quantity: pos.quantity,
                average_cost: pos.average_cost,
                current_price,
                market_value,
                unrealized_pnl,
                unrealized_pnl_percent,
            });

            total_value += market_value * Decimal::from(pos.quantity.signum());
        }

        Ok(Portfolio {
            account_id: account_id.to_string(),
            positions,
            cash_balance: base_portfolio.cash_balance,
            total_value,
            last_updated: Utc::now(),
        })
    }

    
    fn record_metric(&self, account_id: &str, cache_hit: bool) {
        let mut metrics = self.metrics.write();
        let account_metrics = metrics.entry(account_id.to_string())
            .or_insert_with(HashMap::new);

        
        // If you have 1M accounts, you have 1M metric series
        let position_metrics = account_metrics.entry("__portfolio__".to_string())
            .or_insert_with(PositionMetrics::default);

        position_metrics.valuation_count += 1;
        position_metrics.last_valuation_time = Some(Utc::now());

        if cache_hit {
            position_metrics.cache_hits += 1;
        } else {
            position_metrics.cache_misses += 1;
        }
    }

    
    fn record_position_metric(&self, account_id: &str, symbol: &str) {
        let mut metrics = self.metrics.write();
        let account_metrics = metrics.entry(account_id.to_string())
            .or_insert_with(HashMap::new);

        
        let position_metrics = account_metrics.entry(symbol.to_string())
            .or_insert_with(PositionMetrics::default);

        position_metrics.valuation_count += 1;
    }

    pub fn update_position(&self, account_id: &str, symbol: &str, quantity_delta: i64, price: Decimal) -> Result<()> {
        let mut portfolio = self.portfolios.entry(account_id.to_string())
            .or_insert(Portfolio {
                account_id: account_id.to_string(),
                positions: HashMap::new(),
                cash_balance: Decimal::ZERO,
                total_value: Decimal::ZERO,
                last_updated: Utc::now(),
            });

        let position = portfolio.positions.entry(symbol.to_string())
            .or_insert(PortfolioPosition {
                symbol: symbol.to_string(),
                quantity: 0,
                average_cost: Decimal::ZERO,
                current_price: price,
                market_value: Decimal::ZERO,
                unrealized_pnl: Decimal::ZERO,
                unrealized_pnl_percent: Decimal::ZERO,
            });

        // Update position
        let old_qty = position.quantity;
        let new_qty = old_qty + quantity_delta;

        if (old_qty >= 0 && quantity_delta > 0) || (old_qty <= 0 && quantity_delta < 0) {
            // Adding to position - recalculate average
            let old_cost = position.average_cost * Decimal::from(old_qty.abs());
            let new_cost = price * Decimal::from(quantity_delta.abs());
            if new_qty != 0 {
                position.average_cost = (old_cost + new_cost) / Decimal::from(new_qty.abs());
            }
        }

        position.quantity = new_qty;
        position.current_price = price;
        portfolio.last_updated = Utc::now();

        
        // self.valuation_cache.remove(account_id);

        Ok(())
    }

    pub fn update_market_price(&self, symbol: &str, price: Decimal) {
        self.market_prices.insert(symbol.to_string(), price);

        
        // But we don't track which accounts hold which symbols efficiently
    }

    pub fn set_cash_balance(&self, account_id: &str, balance: Decimal) -> Result<()> {
        let mut portfolio = self.portfolios.entry(account_id.to_string())
            .or_insert(Portfolio {
                account_id: account_id.to_string(),
                positions: HashMap::new(),
                cash_balance: Decimal::ZERO,
                total_value: Decimal::ZERO,
                last_updated: Utc::now(),
            });

        portfolio.cash_balance = balance;
        portfolio.last_updated = Utc::now();

        
        Ok(())
    }
}

// Correct implementation for H2 (cache stampede):
// Use singleflight pattern or distributed locking:
//
// impl PortfolioManager {
//     pub async fn get_portfolio(&self, account_id: &str) -> Result<Portfolio> {
//         // Check cache first
//         if let Some(cached) = self.check_cache(account_id) {
//             return Ok(cached);
//         }
//
//         // Use singleflight to coalesce concurrent requests
//         let result = self.singleflight
//             .work(account_id, || async {
//                 self.calculate_portfolio(account_id).await
//             })
//             .await?;
//
//         // Cache result
//         self.update_cache(account_id, &result);
//
//         Ok(result)
//     }
// }

// Correct implementation for J2 (metric cardinality):
// Use bounded labels, not user IDs:
//
// fn record_metric(&self, cache_hit: bool) {
//     // Don't use account_id as label
//     metrics::counter!("portfolio.valuations", "cache_hit" => cache_hit.to_string()).increment(1);
//
//     // Use buckets instead of exact values
//     metrics::histogram!("portfolio.positions.count").record(position_count as f64);
// }

use anyhow::Result;
use dashmap::DashMap;
use parking_lot::RwLock;
use rust_decimal::Decimal;
use rust_decimal_macros::dec;
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::sync::atomic::{AtomicBool, AtomicU64, Ordering};
use std::sync::Arc;
use std::time::{Duration, Instant};




#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum CircuitState {
    Closed,      // Normal operation
    Open,        // Failing, reject requests
    HalfOpen,    // Testing if service recovered
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AccountLimits {
    pub max_position_size: u64,
    pub max_order_size: u64,
    pub max_daily_loss: Decimal,
    pub max_open_orders: u64,
    pub max_notional: Decimal,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SymbolLimits {
    pub max_position_size: u64,
    pub tick_size: Decimal,
    pub lot_size: u64,
    pub min_notional: Decimal,
    pub circuit_breaker_threshold: Decimal,
}

pub struct RiskLimits {
    account_limits: DashMap<String, AccountLimits>,
    symbol_limits: DashMap<String, SymbolLimits>,
    
    circuit_breakers: DashMap<String, CircuitBreaker>,
    
    position_tracker: DashMap<String, DashMap<String, i64>>,  // account -> symbol -> position
}


pub struct CircuitBreaker {
    
    failure_count: AtomicU64,
    success_count: AtomicU64,
    state: RwLock<CircuitState>,
    last_failure: RwLock<Option<Instant>>,
    
    failure_threshold: u64,
    success_threshold: u64,
    timeout: Duration,
}

impl CircuitBreaker {
    pub fn new(failure_threshold: u64, success_threshold: u64, timeout: Duration) -> Self {
        Self {
            failure_count: AtomicU64::new(0),
            success_count: AtomicU64::new(0),
            state: RwLock::new(CircuitState::Closed),
            last_failure: RwLock::new(None),
            failure_threshold,
            success_threshold,
            timeout,
        }
    }

    
    pub fn allow_request(&self) -> bool {
        let state = *self.state.read();

        match state {
            CircuitState::Closed => true,
            CircuitState::Open => {
                
                let last_failure = self.last_failure.read();
                if let Some(last) = *last_failure {
                    if last.elapsed() >= self.timeout {
                        
                        drop(last_failure);
                        let mut state = self.state.write();
                        *state = CircuitState::HalfOpen;
                        self.success_count.store(0, Ordering::Relaxed);
                        return true;
                    }
                }
                false
            }
            CircuitState::HalfOpen => {
                
                true
            }
        }
    }

    
    pub fn record_success(&self) {
        let state = *self.state.read();

        match state {
            CircuitState::HalfOpen => {
                
                let successes = self.success_count.fetch_add(1, Ordering::Relaxed) + 1;

                if successes >= self.success_threshold {
                    
                    let mut state = self.state.write();
                    if *state == CircuitState::HalfOpen {
                        *state = CircuitState::Closed;
                        self.failure_count.store(0, Ordering::Relaxed);
                    }
                }
            }
            CircuitState::Closed => {
                // Reset failure count on success
                
                self.failure_count.store(0, Ordering::Relaxed);
            }
            _ => {}
        }
    }

    
    pub fn record_failure(&self) {
        *self.last_failure.write() = Some(Instant::now());

        let state = *self.state.read();

        match state {
            CircuitState::HalfOpen => {
                
                let mut state = self.state.write();
                *state = CircuitState::Open;
            }
            CircuitState::Closed => {
                
                let failures = self.failure_count.fetch_add(1, Ordering::Relaxed) + 1;

                if failures >= self.failure_threshold {
                    
                    let mut state = self.state.write();
                    if *state == CircuitState::Closed {
                        *state = CircuitState::Open;
                    }
                }
            }
            _ => {}
        }
    }
}

impl RiskLimits {
    pub fn new() -> Self {
        Self {
            account_limits: DashMap::new(),
            symbol_limits: DashMap::new(),
            circuit_breakers: DashMap::new(),
            position_tracker: DashMap::new(),
        }
    }

    
    pub fn check_position_limit(&self, account_id: &str, symbol: &str, delta: i64) -> Result<bool> {
        let account_limits = self.account_limits.get(account_id)
            .ok_or_else(|| anyhow::anyhow!("Account limits not found"))?;

        let symbol_limits = self.symbol_limits.get(symbol)
            .ok_or_else(|| anyhow::anyhow!("Symbol limits not found"))?;

        
        // Another service instance might approve a position that exceeds limits
        let current_position = self.position_tracker
            .get(account_id)
            .and_then(|positions| positions.get(symbol).map(|p| *p))
            .unwrap_or(0);

        let new_position = current_position + delta;

        // Check account limit
        if new_position.unsigned_abs() > account_limits.max_position_size {
            return Ok(false);
        }

        // Check symbol limit
        if new_position.unsigned_abs() > symbol_limits.max_position_size {
            return Ok(false);
        }

        Ok(true)
    }

    
    pub fn reserve_position(&self, account_id: &str, symbol: &str, delta: i64) -> Result<()> {
        
        let account_positions = self.position_tracker
            .entry(account_id.to_string())
            .or_insert_with(DashMap::new);

        let mut position = account_positions
            .entry(symbol.to_string())
            .or_insert(0);

        
        *position += delta;

        Ok(())
    }

    
    pub fn validate_order(&self, symbol: &str, price: Decimal, quantity: u64) -> Result<()> {
        let limits = self.symbol_limits.get(symbol)
            .ok_or_else(|| anyhow::anyhow!("Symbol not found"))?;

        
        // Price should be a multiple of tick_size
        // let remainder = price % limits.tick_size;
        // if remainder != Decimal::ZERO {
        //     return Err(anyhow::anyhow!("Price not on tick"));
        // }

        // Check lot size
        if quantity % limits.lot_size != 0 {
            return Err(anyhow::anyhow!("Quantity not a multiple of lot size"));
        }

        // Check minimum notional
        let notional = price * Decimal::from(quantity);
        if notional < limits.min_notional {
            return Err(anyhow::anyhow!("Order below minimum notional"));
        }

        Ok(())
    }

    pub fn set_account_limits(&self, account_id: &str, limits: AccountLimits) {
        self.account_limits.insert(account_id.to_string(), limits);
    }

    pub fn set_symbol_limits(&self, symbol: &str, limits: SymbolLimits) {
        self.symbol_limits.insert(symbol.to_string(), limits);
    }

    pub fn get_circuit_breaker(&self, name: &str) -> Option<Arc<CircuitBreaker>> {
        self.circuit_breakers.get(name).map(|cb| Arc::new(CircuitBreaker {
            failure_count: AtomicU64::new(cb.failure_count.load(Ordering::Relaxed)),
            success_count: AtomicU64::new(cb.success_count.load(Ordering::Relaxed)),
            state: RwLock::new(*cb.state.read()),
            last_failure: RwLock::new(*cb.last_failure.read()),
            failure_threshold: cb.failure_threshold,
            success_threshold: cb.success_threshold,
            timeout: cb.timeout,
        }))
    }
}

// Correct implementation for G2 (circuit breaker):
// Use a single lock for all state transitions:
//
// pub struct CircuitBreaker {
//     state: RwLock<CircuitBreakerState>,
// }
//
// struct CircuitBreakerState {
//     state: CircuitState,
//     failure_count: u64,
//     success_count: u64,
//     last_failure: Option<Instant>,
// }
//
// impl CircuitBreaker {
//     pub fn record_result(&self, success: bool) {
//         let mut state = self.state.write();
//         if success {
//             match state.state {
//                 CircuitState::HalfOpen => {
//                     state.success_count += 1;
//                     if state.success_count >= self.success_threshold {
//                         state.state = CircuitState::Closed;
//                         state.failure_count = 0;
//                     }
//                 }
//                 CircuitState::Closed => {
//                     state.failure_count = 0;
//                 }
//                 _ => {}
//             }
//         } else {
//             state.last_failure = Some(Instant::now());
//             match state.state {
//                 CircuitState::HalfOpen => {
//                     state.state = CircuitState::Open;
//                 }
//                 CircuitState::Closed => {
//                     state.failure_count += 1;
//                     if state.failure_count >= self.failure_threshold {
//                         state.state = CircuitState::Open;
//                     }
//                 }
//                 _ => {}
//             }
//         }
//     }
// }

// Correct implementation for D1 (distributed limits):
// Use etcd or Redis for distributed locking:
//
// pub async fn check_and_reserve_position(
//     &self,
//     etcd: &EtcdClient,
//     account_id: &str,
//     symbol: &str,
//     delta: i64,
// ) -> Result<()> {
//     let lock_key = format!("/locks/position/{}/{}", account_id, symbol);
//     let lease = etcd.lease_grant(5).await?;
//     let lock = etcd.lock(lock_key, lease.id()).await?;
//
//     // Now we have exclusive access across all instances
//     let current = self.get_distributed_position(etcd, account_id, symbol).await?;
//     let new_position = current + delta;
//
//     if !self.check_limits(account_id, symbol, new_position)? {
//         etcd.unlock(lock).await?;
//         return Err(anyhow::anyhow!("Position limit exceeded"));
//     }
//
//     self.set_distributed_position(etcd, account_id, symbol, new_position).await?;
//     etcd.unlock(lock).await?;
//
//     Ok(())
// }

use anyhow::Result;
use chrono::{DateTime, Utc};
use dashmap::DashMap;
use parking_lot::RwLock;
use rust_decimal::Decimal;
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::sync::Arc;




#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Position {
    pub account_id: String,
    pub symbol: String,
    pub quantity: i64,
    pub average_entry_price: Decimal,
    pub realized_pnl: Decimal,
    pub unrealized_pnl: Decimal,
    pub last_updated: DateTime<Utc>,
    pub version: u64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PositionEvent {
    pub event_id: u64,
    pub account_id: String,
    pub symbol: String,
    pub event_type: PositionEventType,
    pub timestamp: DateTime<Utc>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum PositionEventType {
    Opened { quantity: i64, price: Decimal },
    Increased { quantity: i64, price: Decimal },
    Decreased { quantity: i64, price: Decimal, realized_pnl: Decimal },
    Closed { realized_pnl: Decimal },
    PriceUpdated { price: Decimal },
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PositionSnapshot {
    pub positions: HashMap<String, HashMap<String, Position>>,
    pub last_event_id: u64,
    pub timestamp: DateTime<Utc>,
}

pub struct PositionTracker {
    positions: DashMap<String, DashMap<String, Position>>,  // account -> symbol -> position
    
    event_log: Arc<RwLock<Vec<PositionEvent>>>,
    
    last_snapshot: Arc<RwLock<Option<PositionSnapshot>>>,
    event_counter: std::sync::atomic::AtomicU64,
}

impl PositionTracker {
    pub fn new() -> Self {
        Self {
            positions: DashMap::new(),
            event_log: Arc::new(RwLock::new(Vec::new())),
            last_snapshot: Arc::new(RwLock::new(None)),
            event_counter: std::sync::atomic::AtomicU64::new(0),
        }
    }

    
    pub fn apply_fill(&self, account_id: &str, symbol: &str, quantity: i64, price: Decimal) -> Result<Position> {
        let account_positions = self.positions
            .entry(account_id.to_string())
            .or_insert_with(DashMap::new);

        
        // This can happen if events arrive via different network paths

        let mut position = account_positions
            .entry(symbol.to_string())
            .or_insert(Position {
                account_id: account_id.to_string(),
                symbol: symbol.to_string(),
                quantity: 0,
                average_entry_price: Decimal::ZERO,
                realized_pnl: Decimal::ZERO,
                unrealized_pnl: Decimal::ZERO,
                last_updated: Utc::now(),
                version: 0,
            });

        let event_type = if position.quantity == 0 {
            // Opening new position
            position.quantity = quantity;
            position.average_entry_price = price;
            PositionEventType::Opened { quantity, price }
        } else if (position.quantity > 0 && quantity > 0) || (position.quantity < 0 && quantity < 0) {
            // Increasing position
            let old_value = position.average_entry_price * Decimal::from(position.quantity.abs());
            let add_value = price * Decimal::from(quantity.abs());
            let new_quantity = position.quantity + quantity;

            
            position.average_entry_price = (old_value + add_value) / Decimal::from(new_quantity.abs());
            position.quantity = new_quantity;

            PositionEventType::Increased { quantity, price }
        } else {
            // Decreasing or closing position
            let close_qty = quantity.abs().min(position.quantity.abs());
            let pnl_per_unit = if position.quantity > 0 {
                price - position.average_entry_price
            } else {
                position.average_entry_price - price
            };
            let realized_pnl = pnl_per_unit * Decimal::from(close_qty);
            position.realized_pnl += realized_pnl;

            let new_quantity = position.quantity + quantity;
            position.quantity = new_quantity;

            if new_quantity == 0 {
                PositionEventType::Closed { realized_pnl }
            } else {
                PositionEventType::Decreased { quantity, price, realized_pnl }
            }
        };

        
        // Another thread might read inconsistent state
        position.version += 1;
        position.last_updated = Utc::now();

        
        let event_id = self.event_counter.fetch_add(1, std::sync::atomic::Ordering::Relaxed);
        let event = PositionEvent {
            event_id,
            account_id: account_id.to_string(),
            symbol: symbol.to_string(),
            event_type,
            timestamp: position.last_updated,
        };

        self.event_log.write().push(event);

        Ok(position.clone())
    }

    
    pub fn create_snapshot(&self) -> PositionSnapshot {
        
        // No coordination between snapshot and position updates
        let mut positions_map: HashMap<String, HashMap<String, Position>> = HashMap::new();

        
        // Concurrent modifications may cause some positions to be missed or duplicated
        for account_entry in self.positions.iter() {
            let account_id = account_entry.key().clone();
            let mut symbol_positions = HashMap::new();

            for pos_entry in account_entry.value().iter() {
                
                symbol_positions.insert(pos_entry.key().clone(), pos_entry.value().clone());
            }

            positions_map.insert(account_id, symbol_positions);
        }

        
        // Events might have been added after we started iterating positions
        let last_event_id = self.event_counter.load(std::sync::atomic::Ordering::Relaxed);

        let snapshot = PositionSnapshot {
            positions: positions_map,
            last_event_id,
            timestamp: Utc::now(),
        };

        *self.last_snapshot.write() = Some(snapshot.clone());

        snapshot
    }

    
    pub fn rebuild_from_events(&self, events: &[PositionEvent]) -> Result<HashMap<String, HashMap<String, Position>>> {
        let mut positions: HashMap<String, HashMap<String, Position>> = HashMap::new();

        
        // If events arrive out of order, state will be wrong

        for event in events {
            let account_positions = positions
                .entry(event.account_id.clone())
                .or_insert_with(HashMap::new);

            let position = account_positions
                .entry(event.symbol.clone())
                .or_insert(Position {
                    account_id: event.account_id.clone(),
                    symbol: event.symbol.clone(),
                    quantity: 0,
                    average_entry_price: Decimal::ZERO,
                    realized_pnl: Decimal::ZERO,
                    unrealized_pnl: Decimal::ZERO,
                    last_updated: event.timestamp,
                    version: 0,
                });

            match &event.event_type {
                PositionEventType::Opened { quantity, price } => {
                    position.quantity = *quantity;
                    position.average_entry_price = *price;
                }
                PositionEventType::Increased { quantity, price } => {
                    
                    // Events don't contain enough info to replay correctly
                    let old_value = position.average_entry_price * Decimal::from(position.quantity.abs());
                    let add_value = price * Decimal::from(quantity.abs());
                    position.quantity += quantity;
                    if position.quantity != 0 {
                        position.average_entry_price = (old_value + add_value) / Decimal::from(position.quantity.abs());
                    }
                }
                PositionEventType::Decreased { quantity, realized_pnl, .. } => {
                    position.quantity += quantity;
                    position.realized_pnl += realized_pnl;
                }
                PositionEventType::Closed { realized_pnl } => {
                    position.quantity = 0;
                    position.realized_pnl += realized_pnl;
                }
                PositionEventType::PriceUpdated { .. } => {
                    // Price updates don't change position state
                }
            }

            position.last_updated = event.timestamp;
            position.version += 1;
        }

        Ok(positions)
    }

    pub fn get_position(&self, account_id: &str, symbol: &str) -> Option<Position> {
        self.positions.get(account_id)
            .and_then(|account| account.get(symbol).map(|p| p.clone()))
    }

    pub fn get_all_positions(&self, account_id: &str) -> Vec<Position> {
        self.positions.get(account_id)
            .map(|account| account.iter().map(|p| p.value().clone()).collect())
            .unwrap_or_default()
    }
}

// Correct implementation for C1 (event ordering):
// Use a sequence number that's atomically assigned with position update:
//
// pub fn apply_fill(&self, account_id: &str, symbol: &str, quantity: i64, price: Decimal, expected_version: u64) -> Result<Position> {
//     let account_positions = self.positions.entry(account_id.to_string()).or_insert_with(DashMap::new);
//
//     loop {
//         let mut position = account_positions.entry(symbol.to_string()).or_insert(...);
//
//         if position.version != expected_version {
//             return Err(anyhow::anyhow!("Version mismatch - concurrent modification"));
//         }
//
//         // Atomically update position and log event
//         position.version += 1;
//         let event = PositionEvent { event_id: position.version, ... };
//
//         // Use a transaction or atomic operation
//         break;
//     }
// }

// Correct implementation for C3 (snapshot):
// Use a read-write lock that coordinates snapshot with updates:
//
// pub fn create_snapshot(&self) -> PositionSnapshot {
//     // Acquire global read lock to prevent modifications during snapshot
//     let _snapshot_lock = self.snapshot_lock.read();
//
//     // Now safe to iterate and create consistent snapshot
//     let positions_map = ...;
//     let last_event_id = self.event_counter.load(Ordering::SeqCst);
//
//     PositionSnapshot { positions: positions_map, last_event_id, timestamp: Utc::now() }
// }

use anyhow::Result;
use chrono::{DateTime, Utc};
use dashmap::DashMap;
use parking_lot::RwLock;
use rust_decimal::Decimal;
use serde::{Deserialize, Serialize};
use shared::types::{OrderId, Price, Quantity, Symbol};
use std::collections::HashMap;
use std::sync::Arc;
use uuid::Uuid;

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum OrderStatus {
    Pending,
    Validated,
    Submitted,
    PartiallyFilled,
    Filled,
    Cancelled,
    Rejected,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum OrderSide {
    Buy,
    Sell,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum OrderType {
    Market,
    Limit,
    StopLimit,
    StopMarket,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Order {
    pub id: Uuid,
    pub client_order_id: String,
    pub account_id: String,
    pub symbol: Symbol,
    pub side: OrderSide,
    pub order_type: OrderType,
    pub price: Option<Decimal>,
    pub stop_price: Option<Decimal>,
    pub quantity: u64,
    pub filled_quantity: u64,
    pub status: OrderStatus,
    pub created_at: DateTime<Utc>,
    pub updated_at: DateTime<Utc>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct OrderEvent {
    pub order_id: Uuid,
    pub event_type: OrderEventType,
    pub timestamp: DateTime<Utc>,
    pub sequence: u64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum OrderEventType {
    Created,
    Validated,
    Submitted,
    PartialFill { quantity: u64, price: Decimal },
    Filled { quantity: u64, price: Decimal },
    Cancelled { reason: String },
    Rejected { reason: String },
}

pub struct OrderService {
    orders: DashMap<Uuid, Arc<RwLock<Order>>>,
    
    events: DashMap<Uuid, Vec<OrderEvent>>,
    
    event_sequence: std::sync::atomic::AtomicU64,
    
    account_orders: DashMap<String, Vec<Uuid>>,
}

impl OrderService {
    pub fn new() -> Self {
        Self {
            orders: DashMap::new(),
            events: DashMap::new(),
            event_sequence: std::sync::atomic::AtomicU64::new(0),
            account_orders: DashMap::new(),
        }
    }

    
    pub async fn create_order(&self, request: CreateOrderRequest) -> Result<Order> {
        let order_id = Uuid::new_v4();
        let now = Utc::now();

        let order = Order {
            id: order_id,
            client_order_id: request.client_order_id,
            account_id: request.account_id.clone(),
            symbol: request.symbol,
            side: request.side,
            order_type: request.order_type,
            price: request.price,
            stop_price: request.stop_price,
            quantity: request.quantity,
            filled_quantity: 0,
            status: OrderStatus::Pending,
            created_at: now,
            updated_at: now,
        };

        
        let sequence = self.event_sequence.fetch_add(1, std::sync::atomic::Ordering::Relaxed);

        let event = OrderEvent {
            order_id,
            event_type: OrderEventType::Created,
            timestamp: now,
            sequence,
        };

        // Store order
        self.orders.insert(order_id, Arc::new(RwLock::new(order.clone())));

        
        self.events.entry(order_id).or_insert_with(Vec::new).push(event);

        // Track account orders
        self.account_orders
            .entry(request.account_id)
            .or_insert_with(Vec::new)
            .push(order_id);

        
        // Should check position limits, buying power, etc.

        Ok(order)
    }

    
    pub async fn cancel_order(&self, order_id: Uuid, reason: String) -> Result<Order> {
        let order_lock = self.orders.get(&order_id)
            .ok_or_else(|| anyhow::anyhow!("Order not found"))?;

        
        // Another thread could modify the order between read and write
        let mut order = order_lock.write();

        
        // should be no-op, not error
        if order.status == OrderStatus::Cancelled {
            
            return Err(anyhow::anyhow!("Order already cancelled"));
        }

        if order.status == OrderStatus::Filled {
            return Err(anyhow::anyhow!("Cannot cancel filled order"));
        }

        order.status = OrderStatus::Cancelled;
        order.updated_at = Utc::now();

        let sequence = self.event_sequence.fetch_add(1, std::sync::atomic::Ordering::Relaxed);
        let event = OrderEvent {
            order_id,
            event_type: OrderEventType::Cancelled { reason },
            timestamp: order.updated_at,
            sequence,
        };

        
        self.events.entry(order_id).or_insert_with(Vec::new).push(event);

        Ok(order.clone())
    }

    
    pub async fn fill_order(&self, order_id: Uuid, fill_qty: u64, fill_price: Decimal) -> Result<Order> {
        let order_lock = self.orders.get(&order_id)
            .ok_or_else(|| anyhow::anyhow!("Order not found"))?;

        let mut order = order_lock.write();

        
        let new_filled = order.filled_quantity + fill_qty;

        
        // Could result in filled_quantity > quantity

        order.filled_quantity = new_filled;
        order.updated_at = Utc::now();

        let event_type = if new_filled >= order.quantity {
            order.status = OrderStatus::Filled;
            OrderEventType::Filled { quantity: fill_qty, price: fill_price }
        } else {
            order.status = OrderStatus::PartiallyFilled;
            OrderEventType::PartialFill { quantity: fill_qty, price: fill_price }
        };

        let sequence = self.event_sequence.fetch_add(1, std::sync::atomic::Ordering::Relaxed);
        let event = OrderEvent {
            order_id,
            event_type,
            timestamp: order.updated_at,
            sequence,
        };

        self.events.entry(order_id).or_insert_with(Vec::new).push(event);

        Ok(order.clone())
    }

    
    pub fn rebuild_order_from_events(&self, order_id: Uuid) -> Result<Order> {
        let events = self.events.get(&order_id)
            .ok_or_else(|| anyhow::anyhow!("No events for order"))?;

        
        // DashMap iteration order is not guaranteed
        let mut sorted_events: Vec<_> = events.iter().cloned().collect();

        
        // Timestamp might have clock skew issues
        sorted_events.sort_by_key(|e| e.timestamp);

        let mut order: Option<Order> = None;

        for event in sorted_events {
            match &event.event_type {
                OrderEventType::Created => {
                    
                    // We can't rebuild the order from events alone!
                    return Err(anyhow::anyhow!("Cannot rebuild: Created event lacks order data"));
                }
                OrderEventType::PartialFill { quantity, price: _ } => {
                    if let Some(ref mut o) = order {
                        o.filled_quantity += quantity;
                        o.status = OrderStatus::PartiallyFilled;
                    }
                }
                OrderEventType::Filled { quantity, price: _ } => {
                    if let Some(ref mut o) = order {
                        o.filled_quantity += quantity;
                        o.status = OrderStatus::Filled;
                    }
                }
                OrderEventType::Cancelled { .. } => {
                    if let Some(ref mut o) = order {
                        o.status = OrderStatus::Cancelled;
                    }
                }
                _ => {}
            }
        }

        order.ok_or_else(|| anyhow::anyhow!("Could not rebuild order"))
    }

    
    pub async fn get_order(&self, order_id: Uuid) -> Result<Order> {
        
        if let Some(order_lock) = self.orders.get(&order_id) {
            let order = order_lock.read();
            return Ok(order.clone());
        }

        
        Err(anyhow::anyhow!("Order not found"))
    }

    pub fn get_account_orders(&self, account_id: &str) -> Vec<Order> {
        let order_ids = match self.account_orders.get(account_id) {
            Some(ids) => ids.clone(),
            None => return Vec::new(),
        };

        
        order_ids.iter()
            .filter_map(|id| {
                self.orders.get(id).map(|lock| lock.read().clone())
            })
            .collect()
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CreateOrderRequest {
    pub client_order_id: String,
    pub account_id: String,
    pub symbol: Symbol,
    pub side: OrderSide,
    pub order_type: OrderType,
    pub price: Option<Decimal>,
    pub stop_price: Option<Decimal>,
    pub quantity: u64,
}

// Correct implementation for C1 (event ordering):
// 1. Use a single-writer pattern or optimistic locking
// 2. Sort by sequence number, not timestamp
// 3. Use atomic operations for sequence generation
// 4. Implement event sourcing with proper snapshots

// Correct implementation for F2 (overflow):
// pub async fn fill_order(&self, order_id: Uuid, fill_qty: u64, fill_price: Decimal) -> Result<Order> {
//     let new_filled = order.filled_quantity.checked_add(fill_qty)
//         .ok_or_else(|| anyhow::anyhow!("Overflow in fill quantity"))?;
//
//     if new_filled > order.quantity {
//         return Err(anyhow::anyhow!("Fill exceeds order quantity"));
//     }
//     // ...
// }

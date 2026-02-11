use std::collections::HashMap;
use std::sync::Arc;
use parking_lot::{Mutex, RwLock};
use rust_decimal::Decimal;
use tokio::sync::mpsc;

use crate::orderbook::OrderBook;

pub struct MatchingEngine {
    
    // order_books and risk_state acquired in different orders
    order_books: Arc<RwLock<HashMap<String, Arc<Mutex<OrderBook>>>>>,
    risk_state: Arc<RwLock<HashMap<String, Arc<Mutex<AccountRisk>>>>>,
    event_sender: mpsc::UnboundedSender<MatchEvent>,
}

pub struct AccountRisk {
    pub account_id: String,
    pub buying_power: Decimal,
    pub margin_used: Decimal,
}

#[derive(Debug, Clone)]
pub struct Order {
    pub id: String,
    pub symbol: String,
    pub account_id: String,
    pub side: Side,
    pub price: Decimal,
    pub quantity: u64,
    pub order_type: OrderType,
}

#[derive(Debug, Clone, Copy, PartialEq)]
pub enum Side {
    Buy,
    Sell,
}

#[derive(Debug, Clone, Copy)]
pub enum OrderType {
    Limit,
    Market,
}

#[derive(Debug)]
pub struct MatchEvent {
    pub trade_id: String,
    pub symbol: String,
    pub price: Decimal,
    pub quantity: u64,
}

impl MatchingEngine {
    pub fn new() -> (Self, mpsc::UnboundedReceiver<MatchEvent>) {
        let (tx, rx) = mpsc::unbounded_channel();
        (
            Self {
                order_books: Arc::new(RwLock::new(HashMap::new())),
                risk_state: Arc::new(RwLock::new(HashMap::new())),
                event_sender: tx,
            },
            rx,
        )
    }

    
    // This acquires order_book lock first, then risk lock
    pub fn submit_order(&self, order: Order) -> Result<String, EngineError> {
        
        let order_books = self.order_books.read();
        let order_book = order_books
            .get(&order.symbol)
            .ok_or(EngineError::SymbolNotFound)?
            .clone();

        let mut book = order_book.lock();

        
        let risk_states = self.risk_state.read();
        let risk = risk_states
            .get(&order.account_id)
            .ok_or(EngineError::AccountNotFound)?
            .clone();

        let mut risk_state = risk.lock();

        // Validate risk
        if !self.check_risk(&order, &risk_state) {
            return Err(EngineError::InsufficientMargin);
        }

        // Process order
        let trades = book.add_order(order.clone());

        // Update risk
        risk_state.margin_used += self.calculate_margin(&order);

        Ok(order.id)
    }

    
    pub fn update_risk_and_cancel(&self, account_id: &str, symbol: &str) -> Result<(), EngineError> {
        
        let risk_states = self.risk_state.read();
        let risk = risk_states
            .get(account_id)
            .ok_or(EngineError::AccountNotFound)?
            .clone();

        let mut risk_state = risk.lock();

        
        // If submit_order is running concurrently with opposite lock order,
        // DEADLOCK!
        let order_books = self.order_books.read();
        let order_book = order_books
            .get(symbol)
            .ok_or(EngineError::SymbolNotFound)?
            .clone();

        let mut book = order_book.lock();

        // Cancel orders and update risk
        let cancelled = book.cancel_all_for_account(account_id);
        risk_state.margin_used = Decimal::ZERO;

        Ok(())
    }

    
    pub fn get_best_prices(&self, symbol: &str) -> Option<(Decimal, Decimal)> {
        let order_books = self.order_books.read();
        let order_book = order_books.get(symbol)?.clone();
        drop(order_books); // Release read lock

        
        let book = order_book.lock();
        let bid = book.best_bid();
        drop(book); // Release lock

        
        let book = order_book.lock();
        let ask = book.best_ask();

        
        // Could return crossed market (bid > ask) which is invalid
        Some((bid?, ask?))
    }

    
    pub unsafe fn fast_price_convert(&self, price_bits: u64) -> f64 {
        
        // Could create NaN, infinity, or denormalized values
        std::mem::transmute::<u64, f64>(price_bits)
    }

    
    pub fn update_last_price(&self, symbol: &str, price: Decimal) {
        
        // Other threads may see stale or partially updated data
        static LAST_PRICES: once_cell::sync::Lazy<dashmap::DashMap<String, std::sync::atomic::AtomicU64>> =
            once_cell::sync::Lazy::new(|| dashmap::DashMap::new());

        let price_bits = price.mantissa() as u64;

        
        LAST_PRICES
            .entry(symbol.to_string())
            .or_insert_with(|| std::sync::atomic::AtomicU64::new(0))
            .store(price_bits, std::sync::atomic::Ordering::Relaxed);

        
        // even after this store completes
    }

    fn check_risk(&self, order: &Order, risk: &AccountRisk) -> bool {
        let required_margin = self.calculate_margin(order);
        risk.buying_power >= required_margin
    }

    fn calculate_margin(&self, order: &Order) -> Decimal {
        order.price * Decimal::from(order.quantity) * Decimal::new(1, 1) // 10% margin
    }
}

#[derive(Debug, thiserror::Error)]
pub enum EngineError {
    #[error("Symbol not found")]
    SymbolNotFound,
    #[error("Account not found")]
    AccountNotFound,
    #[error("Insufficient margin")]
    InsufficientMargin,
}

// Correct implementation for B1:
// Use a consistent lock ordering (e.g., always risk then order_book)
// Or use a single lock for both resources
// Or use lock-free data structures
//
// pub fn submit_order(&self, order: Order) -> Result<String, EngineError> {
//     // Always acquire in same order: risk first, then order_book
//     let risk = self.get_risk_state(&order.account_id)?;
//     let mut risk_state = risk.lock();
//
//     let book = self.get_order_book(&order.symbol)?;
//     let mut order_book = book.lock();
//
//     // Now both locks held in consistent order
//     // ...
// }

// Correct implementation for B3:
// Hold lock for entire operation
// pub fn get_best_prices(&self, symbol: &str) -> Option<(Decimal, Decimal)> {
//     let order_books = self.order_books.read();
//     let order_book = order_books.get(symbol)?;
//     let book = order_book.lock();
//
//     // Get both prices while holding lock
//     let bid = book.best_bid()?;
//     let ask = book.best_ask()?;
//
//     Some((bid, ask))
// }

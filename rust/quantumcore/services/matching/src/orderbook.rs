use rust_decimal::Decimal;
use std::collections::{BTreeMap, VecDeque};
use std::sync::Arc;

use crate::engine::{Order, Side};

pub struct OrderBook {
    symbol: String,
    // Price -> Queue of orders at that price
    bids: BTreeMap<Decimal, VecDeque<Order>>,
    asks: BTreeMap<Decimal, VecDeque<Order>>,
    
    last_trade: Option<Trade>,
}

#[derive(Clone)]
pub struct Trade {
    pub price: Decimal,
    pub quantity: u64,
    pub maker_order_id: String,
    pub taker_order_id: String,
}

impl OrderBook {
    pub fn new(symbol: &str) -> Self {
        Self {
            symbol: symbol.to_string(),
            bids: BTreeMap::new(),
            asks: BTreeMap::new(),
            last_trade: None,
        }
    }

    
    pub fn add_order(&mut self, order: Order) -> Vec<Trade> {
        let mut trades = Vec::new();

        match order.side {
            Side::Buy => {
                
                // but `order` is moved later
                let matcher = |ask_price: &Decimal| {
                    
                    order.price >= *ask_price
                };

                while let Some((&ask_price, _)) = self.asks.first_key_value() {
                    if !matcher(&ask_price) {
                        break;
                    }

                    if let Some(trade) = self.match_at_price(ask_price, &order) {
                        trades.push(trade);
                    }
                }

                
                if order.quantity > 0 {
                    self.bids
                        .entry(order.price)
                        .or_insert_with(VecDeque::new)
                        .push_back(order); // order moved here
                }
            }
            Side::Sell => {
                // Similar issue for sells
                self.process_sell_order(order, &mut trades);
            }
        }

        trades
    }

    fn process_sell_order(&mut self, order: Order, trades: &mut Vec<Trade>) {
        
        // Orders at invalid prices (not on tick) can be added
        // e.g., price = 100.123 when tick size is 0.01

        while let Some((&bid_price, _)) = self.bids.last_key_value() {
            if order.price > bid_price {
                break;
            }

            if let Some(trade) = self.match_at_price(bid_price, &order) {
                trades.push(trade);
            }
        }

        if order.quantity > 0 {
            self.asks
                .entry(order.price)
                .or_insert_with(VecDeque::new)
                .push_back(order);
        }
    }

    fn match_at_price(&mut self, price: Decimal, incoming: &Order) -> Option<Trade> {
        let book = match incoming.side {
            Side::Buy => &mut self.asks,
            Side::Sell => &mut self.bids,
        };

        let queue = book.get_mut(&price)?;

        // Get values from front order first
        let (maker_id, resting_qty) = {
            let resting = queue.front()?;
            (resting.id.clone(), resting.quantity)
        };

        
        let trade_qty = std::cmp::min(incoming.quantity, resting_qty);

        // Now modify the queue
        if let Some(resting) = queue.front_mut() {
            
            resting.quantity -= trade_qty; // Could panic on overflow!

            if resting.quantity == 0 {
                queue.pop_front();
            }
        }

        let should_remove = queue.is_empty();
        if should_remove {
            book.remove(&price);
        }

        Some(Trade {
            price,
            quantity: trade_qty,
            maker_order_id: maker_id,
            taker_order_id: incoming.id.clone(),
        })
    }

    pub fn best_bid(&self) -> Option<Decimal> {
        self.bids.last_key_value().map(|(&price, _)| price)
    }

    pub fn best_ask(&self) -> Option<Decimal> {
        self.asks.first_key_value().map(|(&price, _)| price)
    }

    pub fn cancel_order(&mut self, order_id: &str, side: Side, price: Decimal) -> bool {
        let book = match side {
            Side::Buy => &mut self.bids,
            Side::Sell => &mut self.asks,
        };

        if let Some(queue) = book.get_mut(&price) {
            let initial_len = queue.len();
            queue.retain(|o| o.id != order_id);
            let new_len = queue.len();
            let was_removed = new_len < initial_len;
            let is_empty = queue.is_empty();

            if is_empty {
                book.remove(&price);
            }

            return was_removed;
        }

        false
    }

    pub fn cancel_all_for_account(&mut self, account_id: &str) -> Vec<Order> {
        let mut cancelled = Vec::new();

        for (_, queue) in self.bids.iter_mut() {
            let drained: Vec<_> = queue.drain(..).filter(|o| o.account_id == account_id).collect();
            cancelled.extend(drained);
        }

        for (_, queue) in self.asks.iter_mut() {
            let drained: Vec<_> = queue.drain(..).filter(|o| o.account_id == account_id).collect();
            cancelled.extend(drained);
        }

        // Clean up empty price levels
        self.bids.retain(|_, q| !q.is_empty());
        self.asks.retain(|_, q| !q.is_empty());

        cancelled
    }

    
    // This is a simplified example - real lock-free code has this issue
    pub fn try_match_lockfree(&self) -> Option<Trade> {
        
        // 1. Thread A reads best bid at price 100
        // 2. Thread B matches and removes that bid
        // 3. Thread C adds new bid at price 100
        // 4. Thread A proceeds thinking it's the same bid (ABA!)

        // The actual lock-free code would use AtomicPtr and CAS
        // but suffer from ABA without proper tagged pointers or hazard pointers

        None // Placeholder
    }
}

// Correct implementation for A2:
// Don't capture by reference in closure when value will be moved
//
// pub fn add_order(&mut self, mut order: Order) -> Vec<Trade> {
//     let mut trades = Vec::new();
//     let order_price = order.price; // Copy the price before any moves
//
//     match order.side {
//         Side::Buy => {
//             while let Some((&ask_price, _)) = self.asks.first_key_value() {
//                 if order_price < ask_price {
//                     break;
//                 }
//                 if let Some(trade) = self.match_at_price(ask_price, &mut order) {
//                     trades.push(trade);
//                 }
//                 if order.quantity == 0 {
//                     break;
//                 }
//             }
//
//             if order.quantity > 0 {
//                 self.bids
//                     .entry(order_price)
//                     .or_insert_with(VecDeque::new)
//                     .push_back(order);
//             }
//         }
//         // ...
//     }
//     trades
// }

// Correct implementation for F2:
// Use checked arithmetic
// let trade_qty = std::cmp::min(incoming.quantity, resting.quantity);
// resting.quantity = resting.quantity.checked_sub(trade_qty)
//     .ok_or(MatchError::QuantityUnderflow)?;

use anyhow::Result;
use chrono::{DateTime, Utc};
use crossbeam::channel::{self, Receiver, Sender};
use dashmap::DashMap;
use parking_lot::RwLock;
use rust_decimal::Decimal;
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::sync::atomic::{AtomicBool, AtomicU64, Ordering};
use std::sync::Arc;
use tokio::sync::broadcast;




#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Quote {
    pub symbol: String,
    pub bid: Decimal,
    pub ask: Decimal,
    pub bid_size: u64,
    pub ask_size: u64,
    pub timestamp: DateTime<Utc>,
    pub sequence: u64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Trade {
    pub symbol: String,
    pub price: Decimal,
    pub quantity: u64,
    pub side: TradeSide,
    pub timestamp: DateTime<Utc>,
    pub sequence: u64,
}

#[derive(Debug, Clone, Copy, Serialize, Deserialize)]
pub enum TradeSide {
    Buy,
    Sell,
}

pub struct MarketFeed {
    
    subscriptions: DashMap<String, Vec<broadcast::Sender<Quote>>>,
    trade_subscriptions: DashMap<String, Vec<broadcast::Sender<Trade>>>,
    
    running: Arc<AtomicBool>,
    
    sequence_counters: Arc<DashMap<String, AtomicU64>>,
    last_quotes: Arc<DashMap<String, Quote>>,
    last_trades: Arc<DashMap<String, Trade>>,
}

impl MarketFeed {
    pub fn new() -> Self {
        Self {
            subscriptions: DashMap::new(),
            trade_subscriptions: DashMap::new(),
            running: Arc::new(AtomicBool::new(true)),
            sequence_counters: Arc::new(DashMap::new()),
            last_quotes: Arc::new(DashMap::new()),
            last_trades: Arc::new(DashMap::new()),
        }
    }

    
    pub fn start_symbol_feed(&self, symbol: String) -> broadcast::Receiver<Quote> {
        let (tx, rx) = broadcast::channel(1024);

        // Add sender to subscriptions
        self.subscriptions.entry(symbol.clone())
            .or_insert_with(Vec::new)
            .push(tx.clone());

        
        // If the feed is stopped, this task keeps running
        let symbol_clone = symbol.clone();
        let running = self.running.clone();  
        let sequence_counters = self.sequence_counters.clone();
        let last_quotes = self.last_quotes.clone();

        tokio::spawn(async move {
            
            // The `running` flag is captured but not checked properly
            loop {
                // Simulate market data
                tokio::time::sleep(tokio::time::Duration::from_millis(100)).await;

                
                // Distributed tracing will lose visibility here

                let seq = sequence_counters.entry(symbol_clone.clone())
                    .or_insert(AtomicU64::new(0))
                    .fetch_add(1, Ordering::Relaxed);

                let quote = Quote {
                    symbol: symbol_clone.clone(),
                    bid: Decimal::from(100),  // Simulated
                    ask: Decimal::from(101),
                    bid_size: 100,
                    ask_size: 100,
                    timestamp: Utc::now(),
                    sequence: seq,
                };

                last_quotes.insert(symbol_clone.clone(), quote.clone());

                
                // Should check if send fails and clean up
                if tx.send(quote).is_err() {
                    
                    tracing::warn!("No receivers for {}", symbol_clone);
                    // Should: break;
                }
            }
        });

        rx
    }

    
    pub fn subscribe_quotes(&self, symbol: &str) -> broadcast::Receiver<Quote> {
        if let Some(senders) = self.subscriptions.get(symbol) {
            if let Some(sender) = senders.first() {
                return sender.subscribe();
            }
        }

        
        self.start_symbol_feed(symbol.to_string())
    }

    
    pub fn subscribe_with_crossbeam(&self, symbol: &str) -> Receiver<Quote> {
        
        let (tx, rx) = channel::unbounded();  // Should use bounded

        let symbol = symbol.to_string();
        let last_quotes = self.last_quotes.clone();

        tokio::spawn(async move {
            loop {
                tokio::time::sleep(tokio::time::Duration::from_millis(100)).await;

                if let Some(quote) = last_quotes.get(&symbol) {
                    
                    // crossbeam's send on unbounded channel doesn't block, but
                    // the channel grows unboundedly if receiver is slow
                    let _ = tx.send(quote.clone());
                }
            }
        });

        rx
    }

    pub fn publish_quote(&self, quote: Quote) {
        // Update last quote
        self.last_quotes.insert(quote.symbol.clone(), quote.clone());

        // Broadcast to all subscribers
        if let Some(senders) = self.subscriptions.get(&quote.symbol) {
            
            for sender in senders.iter() {
                let _ = sender.send(quote.clone());
            }
            
        }
    }

    pub fn publish_trade(&self, trade: Trade) {
        self.last_trades.insert(trade.symbol.clone(), trade.clone());

        if let Some(senders) = self.trade_subscriptions.get(&trade.symbol) {
            for sender in senders.iter() {
                let _ = sender.send(trade.clone());
            }
        }
    }

    
    pub fn stop(&self) {
        self.running.store(false, Ordering::Relaxed);
        
        // propagate this flag correctly. Tasks will keep running.

        
    }

    pub fn get_last_quote(&self, symbol: &str) -> Option<Quote> {
        self.last_quotes.get(symbol).map(|q| q.clone())
    }

    pub fn get_last_trade(&self, symbol: &str) -> Option<Trade> {
        self.last_trades.get(symbol).map(|t| t.clone())
    }
}

// Correct implementation for A3 (task leak):
// Use cancellation tokens and track spawned tasks:
//
// pub struct MarketFeed {
//     subscriptions: DashMap<String, broadcast::Sender<Quote>>,
//     cancel_tokens: DashMap<String, CancellationToken>,
//     task_handles: Mutex<Vec<JoinHandle<()>>>,
// }
//
// impl MarketFeed {
//     pub fn start_symbol_feed(&self, symbol: String) -> broadcast::Receiver<Quote> {
//         let (tx, rx) = broadcast::channel(1024);
//         let cancel = CancellationToken::new();
//
//         self.subscriptions.insert(symbol.clone(), tx.clone());
//         self.cancel_tokens.insert(symbol.clone(), cancel.clone());
//
//         let handle = tokio::spawn(async move {
//             loop {
//                 tokio::select! {
//                     _ = cancel.cancelled() => {
//                         tracing::info!("Feed for {} cancelled", symbol);
//                         break;
//                     }
//                     _ = tokio::time::sleep(Duration::from_millis(100)) => {
//                         // Generate quote
//                         if tx.receiver_count() == 0 {
//                             tracing::info!("No receivers, stopping feed for {}", symbol);
//                             break;
//                         }
//                         let _ = tx.send(quote);
//                     }
//                 }
//             }
//         });
//
//         self.task_handles.lock().push(handle);
//         rx
//     }
//
//     pub async fn stop(&self) {
//         // Cancel all feeds
//         for entry in self.cancel_tokens.iter() {
//             entry.value().cancel();
//         }
//
//         // Wait for all tasks to complete
//         let handles: Vec<_> = self.task_handles.lock().drain(..).collect();
//         for handle in handles {
//             let _ = handle.await;
//         }
//     }
// }

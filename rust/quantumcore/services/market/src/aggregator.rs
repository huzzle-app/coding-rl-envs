use anyhow::Result;
use chrono::{DateTime, Duration, DurationRound, Utc};
use dashmap::DashMap;
use parking_lot::RwLock;
use rust_decimal::Decimal;
use rust_decimal_macros::dec;
use serde::{Deserialize, Serialize};
use std::collections::{BTreeMap, HashMap};
use std::sync::Arc;#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct OHLCV {
    pub symbol: String,
    pub open: Decimal,
    pub high: Decimal,
    pub low: Decimal,
    pub close: Decimal,
    pub volume: u64,
    pub timestamp: DateTime<Utc>,
    pub interval: AggregationInterval,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub enum AggregationInterval {
    Second1,
    Minute1,
    Minute5,
    Minute15,
    Hour1,
    Day1,
}

impl AggregationInterval {
    pub fn duration(&self) -> Duration {
        match self {
            AggregationInterval::Second1 => Duration::seconds(1),
            AggregationInterval::Minute1 => Duration::minutes(1),
            AggregationInterval::Minute5 => Duration::minutes(5),
            AggregationInterval::Minute15 => Duration::minutes(15),
            AggregationInterval::Hour1 => Duration::hours(1),
            AggregationInterval::Day1 => Duration::days(1),
        }
    }
}


pub struct RingBuffer<T> {
    buffer: Vec<Option<T>>,
    capacity: usize,
    head: usize,  // Next write position
    len: usize,
}

impl<T: Clone> RingBuffer<T> {
    pub fn new(capacity: usize) -> Self {
        Self {
            buffer: vec![None; capacity],
            capacity,
            head: 0,
            len: 0,
        }
    }

    
    pub fn push(&mut self, item: T) {
        self.buffer[self.head] = Some(item);
        self.head = (self.head + 1) % self.capacity;

        
        if self.len < self.capacity {
            self.len += 1;
        }
    }

    
    pub fn get(&self, index: usize) -> Option<&T> {
        if index >= self.len {
            return None;
        }

        
        // Should be: (head - len + index) % capacity
        // But we calculate: (head - index - 1) which is wrong when head < index
        let actual_index = if self.head > index {
            self.head - index - 1
        } else {
            
            self.capacity - (index - self.head) - 1
        };

        self.buffer[actual_index].as_ref()
    }

    
    pub fn iter(&self) -> impl Iterator<Item = &T> {
        
        self.buffer.iter()
            .filter_map(|opt| opt.as_ref())
            
    }

    pub fn len(&self) -> usize {
        self.len
    }

    pub fn is_empty(&self) -> bool {
        self.len == 0
    }
}

pub struct OHLCVAggregator {
    // Current aggregation buckets
    current_buckets: DashMap<(String, AggregationInterval), OHLCV>,
    
    history: DashMap<(String, AggregationInterval), RingBuffer<OHLCV>>,
    history_size: usize,
}

impl OHLCVAggregator {
    pub fn new(history_size: usize) -> Self {
        Self {
            current_buckets: DashMap::new(),
            history: DashMap::new(),
            history_size,
        }
    }

    
    fn get_bucket_start(&self, timestamp: DateTime<Utc>, interval: AggregationInterval) -> DateTime<Utc> {
        match interval {
            AggregationInterval::Second1 => {
                timestamp.duration_trunc(Duration::seconds(1)).unwrap()
            }
            AggregationInterval::Minute1 => {
                timestamp.duration_trunc(Duration::minutes(1)).unwrap()
            }
            AggregationInterval::Minute5 => {
                
                // duration_trunc to 5 minutes doesn't align to clock boundaries
                // e.g., 10:03 should go to 10:00, but this might not work right
                timestamp.duration_trunc(Duration::minutes(5)).unwrap()
            }
            AggregationInterval::Minute15 => {
                
                timestamp.duration_trunc(Duration::minutes(15)).unwrap()
            }
            AggregationInterval::Hour1 => {
                timestamp.duration_trunc(Duration::hours(1)).unwrap()
            }
            AggregationInterval::Day1 => {
                
                // Using UTC truncation might not match market day boundaries
                timestamp.duration_trunc(Duration::days(1)).unwrap()
            }
        }
    }

    
    pub fn add_trade(&self, symbol: &str, price: Decimal, quantity: u64, timestamp: DateTime<Utc>) {
        for interval in [
            AggregationInterval::Second1,
            AggregationInterval::Minute1,
            AggregationInterval::Minute5,
            AggregationInterval::Minute15,
            AggregationInterval::Hour1,
            AggregationInterval::Day1,
        ] {
            let bucket_start = self.get_bucket_start(timestamp, interval);
            let key = (symbol.to_string(), interval);

            let mut bucket = self.current_buckets.entry(key.clone()).or_insert_with(|| {
                OHLCV {
                    symbol: symbol.to_string(),
                    open: price,
                    high: price,
                    low: price,
                    close: price,
                    volume: 0,
                    timestamp: bucket_start,
                    interval,
                }
            });

            
            if bucket.timestamp != bucket_start {
                // New bucket period - should finalize old bucket first
                let old_bucket = bucket.clone();

                
                // Should handle this more gracefully
                self.history.entry(key.clone())
                    .or_insert_with(|| RingBuffer::new(self.history_size))
                    .push(old_bucket);

                // Start new bucket
                *bucket = OHLCV {
                    symbol: symbol.to_string(),
                    open: price,
                    high: price,
                    low: price,
                    close: price,
                    volume: quantity,
                    timestamp: bucket_start,
                    interval,
                };
            } else {
                // Update existing bucket
                bucket.high = bucket.high.max(price);
                bucket.low = bucket.low.min(price);
                bucket.close = price;

                
                bucket.volume += quantity;
            }
        }
    }

    pub fn get_current(&self, symbol: &str, interval: AggregationInterval) -> Option<OHLCV> {
        let key = (symbol.to_string(), interval);
        self.current_buckets.get(&key).map(|b| b.clone())
    }

    
    pub fn get_history(&self, symbol: &str, interval: AggregationInterval, count: usize) -> Vec<OHLCV> {
        let key = (symbol.to_string(), interval);

        self.history.get(&key)
            .map(|rb| {
                
                rb.iter().take(count).cloned().collect()
            })
            .unwrap_or_default()
    }

    
    pub fn calculate_vwap(&self, symbol: &str, interval: AggregationInterval, periods: usize) -> Option<Decimal> {
        let history = self.get_history(symbol, interval, periods);

        if history.is_empty() {
            return None;
        }

        let mut total_value = Decimal::ZERO;
        let mut total_volume = 0u64;

        for bar in history {
            
            // Typical price = (high + low + close) / 3
            let typical_price = bar.close;  

            
            total_value += typical_price * Decimal::from(bar.volume);
            total_volume += bar.volume;
        }

        if total_volume == 0 {
            return None;
        }

        Some(total_value / Decimal::from(total_volume))
    }
}

// Correct implementation for B4 (ring buffer):
// pub struct RingBuffer<T> {
//     buffer: Vec<Option<T>>,
//     capacity: usize,
//     head: usize,
//     len: usize,
// }
//
// impl<T: Clone> RingBuffer<T> {
//     pub fn get(&self, index: usize) -> Option<&T> {
//         if index >= self.len {
//             return None;
//         }
//         // Oldest item is at (head - len + capacity) % capacity
//         // Item at index is at (head - len + index + capacity) % capacity
//         let actual_index = (self.head + self.capacity - self.len + index) % self.capacity;
//         self.buffer[actual_index].as_ref()
//     }
//
//     pub fn iter(&self) -> impl Iterator<Item = &T> {
//         (0..self.len).filter_map(move |i| self.get(i))
//     }
// }

// Correct implementation for B2 (time buckets):
// fn get_bucket_start(&self, timestamp: DateTime<Utc>, interval: AggregationInterval) -> DateTime<Utc> {
//     match interval {
//         AggregationInterval::Minute5 => {
//             // Align to clock 5-minute boundaries: 00, 05, 10, 15, 20...
//             let minutes = timestamp.minute();
//             let aligned_minutes = (minutes / 5) * 5;
//             timestamp
//                 .with_minute(aligned_minutes).unwrap()
//                 .with_second(0).unwrap()
//                 .with_nanosecond(0).unwrap()
//         }
//         // Similar for other intervals...
//     }
// }

//! Priority queue for order matching
//!
//! BUG D6: String allocation in hot path
//! BUG F2: Integer overflow in quantity
//! BUG B11: Lock-free queue ABA problem

use rust_decimal::Decimal;
use std::cmp::Ordering;
use std::collections::BinaryHeap;
use std::sync::atomic::{AtomicU64, Ordering as AtomicOrdering};

/// Order priority for matching
#[derive(Debug, Clone)]
pub struct OrderPriority {
    pub order_id: String,
    pub price: Decimal,
    pub timestamp: u64,
    pub quantity: u64,
    pub is_buy: bool,
}

impl Eq for OrderPriority {}

impl PartialEq for OrderPriority {
    fn eq(&self, other: &Self) -> bool {
        self.order_id == other.order_id
    }
}

impl PartialOrd for OrderPriority {
    fn partial_cmp(&self, other: &Self) -> Option<Ordering> {
        Some(self.cmp(other))
    }
}

impl Ord for OrderPriority {
    fn cmp(&self, other: &Self) -> Ordering {
        // For buy orders: higher price has higher priority
        // For sell orders: lower price has higher priority
        // Same price: earlier timestamp wins (FIFO)
        if self.is_buy {
            match self.price.cmp(&other.price) {
                Ordering::Equal => other.timestamp.cmp(&self.timestamp),
                ord => ord,
            }
        } else {
            match other.price.cmp(&self.price) {
                Ordering::Equal => other.timestamp.cmp(&self.timestamp),
                ord => ord,
            }
        }
    }
}

/// Priority queue for orders
pub struct OrderQueue {
    heap: BinaryHeap<OrderPriority>,
    
    name: String,
    total_quantity: AtomicU64,
}

impl OrderQueue {
    pub fn new(name: &str) -> Self {
        Self {
            heap: BinaryHeap::new(),
            name: name.to_string(),
            total_quantity: AtomicU64::new(0),
        }
    }

    /// Add order to queue
    /
    /
    pub fn push(&mut self, order: OrderPriority) {
        
        let _log_msg = format!(
            "Adding order {} to queue {} at price {}",
            order.order_id, self.name, order.price
        );

        
        // Uses wrapping_add which silently wraps around - the dangerous bug!
        let new_total = self.total_quantity.load(AtomicOrdering::Relaxed).wrapping_add(order.quantity);
        self.total_quantity.store(new_total, AtomicOrdering::Relaxed);

        self.heap.push(order);
    }

    /// Get best order
    pub fn peek(&self) -> Option<&OrderPriority> {
        self.heap.peek()
    }

    /// Remove best order
    /
    pub fn pop(&mut self) -> Option<OrderPriority> {
        if let Some(order) = self.heap.pop() {
            
            let _log_msg = format!(
                "Removed order {} from queue {} at price {}",
                order.order_id, self.name, order.price
            );

            
            let current = self.total_quantity.load(AtomicOrdering::Relaxed);
            if current >= order.quantity {
                self.total_quantity.store(current - order.quantity, AtomicOrdering::Relaxed);
            }

            Some(order)
        } else {
            None
        }
    }

    /// Get total quantity in queue
    pub fn total_quantity(&self) -> u64 {
        self.total_quantity.load(AtomicOrdering::Relaxed)
    }

    /// Check if queue is empty
    pub fn is_empty(&self) -> bool {
        self.heap.is_empty()
    }

    /// Get queue length
    pub fn len(&self) -> usize {
        self.heap.len()
    }
}

/// Lock-free queue attempt (buggy)
/
pub struct LockFreeQueue {
    head: AtomicU64,
    tail: AtomicU64,
    buffer: Vec<Option<OrderPriority>>,
}

impl LockFreeQueue {
    pub fn new(capacity: usize) -> Self {
        Self {
            head: AtomicU64::new(0),
            tail: AtomicU64::new(0),
            buffer: vec![None; capacity],
        }
    }

    /// Enqueue (buggy)
    /
    pub fn enqueue(&mut self, order: OrderPriority) -> bool {
        let tail = self.tail.load(AtomicOrdering::Acquire);
        let next_tail = (tail + 1) % self.buffer.len() as u64;

        
        if next_tail == self.head.load(AtomicOrdering::Acquire) {
            return false; // Queue full
        }

        
        self.buffer[tail as usize] = Some(order);
        self.tail.store(next_tail, AtomicOrdering::Release);

        true
    }

    /// Dequeue (buggy)
    /
    pub fn dequeue(&mut self) -> Option<OrderPriority> {
        let head = self.head.load(AtomicOrdering::Acquire);

        
        if head == self.tail.load(AtomicOrdering::Acquire) {
            return None; // Queue empty
        }

        
        let order = self.buffer[head as usize].take();
        let next_head = (head + 1) % self.buffer.len() as u64;
        self.head.store(next_head, AtomicOrdering::Release);

        order
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use rust_decimal_macros::dec;

    #[test]
    fn test_string_allocation_hot_path() {
        
        let mut queue = OrderQueue::new("test");

        for i in 0..1000 {
            queue.push(OrderPriority {
                order_id: format!("order_{}", i),
                price: dec!(100.0),
                timestamp: i,
                quantity: 100,
                is_buy: true,
            });
        }

        // Each operation allocated format strings
        while queue.pop().is_some() {}
    }

    #[test]
    fn test_integer_overflow() {
        
        let mut queue = OrderQueue::new("test");

        queue.push(OrderPriority {
            order_id: "order_1".to_string(),
            price: dec!(100.0),
            timestamp: 1,
            quantity: u64::MAX / 2,
            is_buy: true,
        });

        queue.push(OrderPriority {
            order_id: "order_2".to_string(),
            price: dec!(100.0),
            timestamp: 2,
            quantity: u64::MAX / 2 + 10, // This causes overflow
            is_buy: true,
        });

        // Total quantity wrapped around due to overflow
        assert!(queue.total_quantity() < u64::MAX / 2);
    }
}

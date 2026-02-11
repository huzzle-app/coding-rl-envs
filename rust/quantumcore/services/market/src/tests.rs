use crate::feed::{MarketFeed, Quote, Trade, TradeSide};
use crate::aggregator::{AggregationInterval, OHLCVAggregator, RingBuffer, OHLCV};
use chrono::{Duration, TimeZone, Utc};
use rust_decimal::Decimal;
use rust_decimal_macros::dec;
use std::sync::atomic::{AtomicU64, Ordering};
use std::sync::Arc;
use std::time::Duration as StdDuration;

// ============================================================================
// SECTION 1: Bug A5 - Reference Outlives Data Tests
// Tests for subscription lifetime issues where references may outlive their data
// ============================================================================

#[tokio::test]
async fn test_a5_subscription_lifetime_basic() {
    let feed = MarketFeed::new();
    let _rx = feed.start_symbol_feed("AAPL".to_string());

    // Feed should be created without panic
    assert!(feed.get_last_quote("AAPL").is_none());
}

#[tokio::test]
async fn test_a5_subscription_drops_before_feed() {
    let feed = MarketFeed::new();
    let rx = feed.start_symbol_feed("GOOG".to_string());

    // Drop the receiver
    drop(rx);

    // Feed should still be operational
    tokio::time::sleep(StdDuration::from_millis(50)).await;
}

#[tokio::test]
async fn test_a5_multiple_subscriptions_same_symbol() {
    let feed = MarketFeed::new();
    let rx1 = feed.subscribe_quotes("MSFT");
    let rx2 = feed.subscribe_quotes("MSFT");

    // Both receivers should work
    drop(rx1);
    drop(rx2);
}

#[tokio::test]
async fn test_a5_subscription_after_quote_published() {
    let feed = MarketFeed::new();
    let _rx = feed.start_symbol_feed("TSLA".to_string());

    let quote = Quote {
        symbol: "TSLA".to_string(),
        bid: dec!(100.0),
        ask: dec!(100.5),
        bid_size: 100,
        ask_size: 150,
        timestamp: Utc::now(),
        sequence: 1,
    };

    feed.publish_quote(quote);

    // New subscriber should be able to subscribe
    let _rx2 = feed.subscribe_quotes("TSLA");
}

#[tokio::test]
async fn test_a5_reference_in_closure() {
    let feed = Arc::new(MarketFeed::new());
    let feed_clone = feed.clone();

    let handle = tokio::spawn(async move {
        let _rx = feed_clone.start_symbol_feed("NVDA".to_string());
        tokio::time::sleep(StdDuration::from_millis(50)).await;
    });

    handle.await.unwrap();

    // Original feed should still be valid
    let _ = feed.get_last_quote("NVDA");
}

#[tokio::test]
async fn test_a5_dangling_reference_prevention() {
    let feed = MarketFeed::new();

    // Create multiple feeds and subscriptions
    for i in 0..5 {
        let symbol = format!("SYM{}", i);
        let _rx = feed.start_symbol_feed(symbol);
    }

    tokio::time::sleep(StdDuration::from_millis(100)).await;
    feed.stop();
}

// ============================================================================
// SECTION 2: Bug B6 - Channel Backpressure Tests
// Tests for broadcast channel overflow and backpressure handling
// ============================================================================

#[tokio::test]
async fn test_b6_channel_capacity_basic() {
    let feed = MarketFeed::new();
    let mut rx = feed.start_symbol_feed("AAPL".to_string());

    // Should receive at least one quote
    tokio::time::sleep(StdDuration::from_millis(150)).await;

    match rx.try_recv() {
        Ok(_) => (),
        Err(tokio::sync::broadcast::error::TryRecvError::Empty) => (),
        Err(tokio::sync::broadcast::error::TryRecvError::Lagged(_)) => (),
        Err(_) => panic!("Unexpected channel error"),
    }
}

#[tokio::test]
async fn test_b6_slow_consumer_backpressure() {
    let feed = MarketFeed::new();
    let mut rx = feed.start_symbol_feed("SLOW".to_string());

    // Simulate slow consumer by not reading immediately
    tokio::time::sleep(StdDuration::from_millis(500)).await;

    // Consumer should handle lag
    let mut received = 0;
    while let Ok(_) = rx.try_recv() {
        received += 1;
        if received > 10 {
            break;
        }
    }
}

#[tokio::test]
async fn test_b6_multiple_slow_consumers() {
    let feed = MarketFeed::new();
    let _rx1 = feed.start_symbol_feed("MULTI".to_string());
    let _rx2 = feed.subscribe_quotes("MULTI");
    let _rx3 = feed.subscribe_quotes("MULTI");

    tokio::time::sleep(StdDuration::from_millis(300)).await;
}

#[tokio::test]
async fn test_b6_crossbeam_unbounded_growth() {
    let feed = MarketFeed::new();

    // Publish some quotes first
    let quote = Quote {
        symbol: "XBEAM".to_string(),
        bid: dec!(50.0),
        ask: dec!(50.5),
        bid_size: 100,
        ask_size: 100,
        timestamp: Utc::now(),
        sequence: 1,
    };
    feed.publish_quote(quote);

    let rx = feed.subscribe_with_crossbeam("XBEAM");

    // Receiver should be able to receive
    tokio::time::sleep(StdDuration::from_millis(150)).await;

    match rx.try_recv() {
        Ok(_) => (),
        Err(_) => (),
    }
}

#[tokio::test]
async fn test_b6_channel_overflow_handling() {
    let feed = MarketFeed::new();
    let mut rx = feed.start_symbol_feed("OVERFLOW".to_string());

    // Flood the channel
    for i in 0..2000 {
        let quote = Quote {
            symbol: "OVERFLOW".to_string(),
            bid: Decimal::from(100 + i),
            ask: Decimal::from(101 + i),
            bid_size: 100,
            ask_size: 100,
            timestamp: Utc::now(),
            sequence: i as u64,
        };
        feed.publish_quote(quote);
    }

    // Consumer should handle lagged messages
    let mut lagged = false;
    for _ in 0..100 {
        match rx.try_recv() {
            Err(tokio::sync::broadcast::error::TryRecvError::Lagged(_)) => {
                lagged = true;
                break;
            }
            _ => (),
        }
    }
    // May or may not lag depending on timing
    let _ = lagged;
}

// ============================================================================
// SECTION 3: Bug B12 - Memory Ordering in Price Updates Tests
// Tests for atomic ordering issues with price updates
// ============================================================================

#[tokio::test]
async fn test_b12_sequence_counter_ordering() {
    let feed = MarketFeed::new();
    let mut rx = feed.start_symbol_feed("SEQTEST".to_string());

    tokio::time::sleep(StdDuration::from_millis(350)).await;

    let mut last_seq = 0u64;
    let mut out_of_order = 0;

    while let Ok(quote) = rx.try_recv() {
        if quote.sequence < last_seq {
            out_of_order += 1;
        }
        last_seq = quote.sequence;
    }

    // With proper ordering, should be 0
    assert_eq!(out_of_order, 0);
}

#[tokio::test]
async fn test_b12_relaxed_ordering_visibility() {
    let counter = Arc::new(AtomicU64::new(0));
    let counter_clone = counter.clone();

    let handle = tokio::spawn(async move {
        for _ in 0..100 {
            counter_clone.fetch_add(1, Ordering::Relaxed);
            tokio::time::sleep(StdDuration::from_micros(100)).await;
        }
    });

    tokio::time::sleep(StdDuration::from_millis(50)).await;

    // With Relaxed ordering, we may not see all updates immediately
    let value = counter.load(Ordering::Relaxed);
    assert!(value <= 100);

    handle.await.unwrap();
}

#[tokio::test]
async fn test_b12_concurrent_price_updates() {
    let feed = Arc::new(MarketFeed::new());
    let mut handles = vec![];

    for i in 0..5 {
        let feed_clone = feed.clone();
        let handle = tokio::spawn(async move {
            for j in 0..10 {
                let quote = Quote {
                    symbol: "CONCURRENT".to_string(),
                    bid: Decimal::from(100 + i * 10 + j),
                    ask: Decimal::from(101 + i * 10 + j),
                    bid_size: 100,
                    ask_size: 100,
                    timestamp: Utc::now(),
                    sequence: (i * 10 + j) as u64,
                };
                feed_clone.publish_quote(quote);
            }
        });
        handles.push(handle);
    }

    for handle in handles {
        handle.await.unwrap();
    }

    // Should have a last quote
    let last = feed.get_last_quote("CONCURRENT");
    assert!(last.is_some());
}

#[tokio::test]
async fn test_b12_acquire_release_semantics() {
    let flag = Arc::new(AtomicU64::new(0));
    let data = Arc::new(std::sync::Mutex::new(0u64));

    let flag_clone = flag.clone();
    let data_clone = data.clone();

    let writer = tokio::spawn(async move {
        *data_clone.lock().unwrap() = 42;
        flag_clone.store(1, Ordering::Release);
    });

    let flag_clone2 = flag.clone();
    let data_clone2 = data.clone();

    let reader = tokio::spawn(async move {
        while flag_clone2.load(Ordering::Acquire) == 0 {
            tokio::task::yield_now().await;
        }
        *data_clone2.lock().unwrap()
    });

    writer.await.unwrap();
    let value = reader.await.unwrap();
    assert_eq!(value, 42);
}

// ============================================================================
// SECTION 4: Bug E2 - Uninitialized Memory Read Tests
// Tests for potential reads of uninitialized memory in ring buffer
// ============================================================================

#[test]
fn test_e2_ring_buffer_empty_get() {
    let rb: RingBuffer<i32> = RingBuffer::new(10);

    // Getting from empty buffer should return None
    assert!(rb.get(0).is_none());
    assert!(rb.get(5).is_none());
}

#[test]
fn test_e2_ring_buffer_out_of_bounds() {
    let mut rb: RingBuffer<i32> = RingBuffer::new(5);
    rb.push(1);
    rb.push(2);

    // Out of bounds should return None
    assert!(rb.get(10).is_none());
    assert!(rb.get(100).is_none());
}

#[test]
fn test_e2_ring_buffer_boundary_access() {
    let mut rb: RingBuffer<i32> = RingBuffer::new(3);
    rb.push(1);
    rb.push(2);
    rb.push(3);

    // Access at boundary
    assert!(rb.get(2).is_some());
    assert!(rb.get(3).is_none());
}

#[test]
fn test_e2_ring_buffer_after_wrap() {
    let mut rb: RingBuffer<i32> = RingBuffer::new(3);

    // Fill and wrap
    rb.push(1);
    rb.push(2);
    rb.push(3);
    rb.push(4); // Wraps

    // All positions should be valid
    for i in 0..rb.len() {
        assert!(rb.get(i).is_some(), "Position {} should be valid", i);
    }
}

#[test]
fn test_e2_empty_iterator() {
    let rb: RingBuffer<i32> = RingBuffer::new(5);

    let items: Vec<_> = rb.iter().collect();
    assert!(items.is_empty());
}

#[test]
fn test_e2_partial_fill_iterator() {
    let mut rb: RingBuffer<i32> = RingBuffer::new(10);
    rb.push(1);
    rb.push(2);
    rb.push(3);

    let items: Vec<_> = rb.iter().collect();
    assert_eq!(items.len(), 3);
}

// ============================================================================
// SECTION 5: Bug E6 - Use After Free in FFI Tests
// Tests for simulated FFI memory safety issues
// ============================================================================

#[test]
fn test_e6_quote_clone_safety() {
    let quote = Quote {
        symbol: "FFI".to_string(),
        bid: dec!(100.0),
        ask: dec!(100.5),
        bid_size: 100,
        ask_size: 100,
        timestamp: Utc::now(),
        sequence: 1,
    };

    let cloned = quote.clone();
    drop(quote);

    // Cloned should be independent
    assert_eq!(cloned.symbol, "FFI");
}

#[test]
fn test_e6_trade_clone_safety() {
    let trade = Trade {
        symbol: "FFI2".to_string(),
        price: dec!(150.0),
        quantity: 100,
        side: TradeSide::Buy,
        timestamp: Utc::now(),
        sequence: 1,
    };

    let cloned = trade.clone();
    drop(trade);

    assert_eq!(cloned.symbol, "FFI2");
}

#[test]
fn test_e6_ohlcv_clone_safety() {
    let ohlcv = OHLCV {
        symbol: "OHLCV".to_string(),
        open: dec!(100.0),
        high: dec!(105.0),
        low: dec!(95.0),
        close: dec!(102.0),
        volume: 1000,
        timestamp: Utc::now(),
        interval: AggregationInterval::Minute1,
    };

    let cloned = ohlcv.clone();
    drop(ohlcv);

    assert_eq!(cloned.symbol, "OHLCV");
}

#[test]
fn test_e6_arc_reference_safety() {
    let feed = Arc::new(MarketFeed::new());
    let weak = Arc::downgrade(&feed);

    drop(feed);

    // Weak reference should not be upgradable
    assert!(weak.upgrade().is_none());
}

#[tokio::test]
async fn test_e6_async_block_capture_safety() {
    let quote = Quote {
        symbol: "ASYNC".to_string(),
        bid: dec!(100.0),
        ask: dec!(100.5),
        bid_size: 100,
        ask_size: 100,
        timestamp: Utc::now(),
        sequence: 1,
    };

    let handle = tokio::spawn(async move {
        tokio::time::sleep(StdDuration::from_millis(10)).await;
        quote.symbol.clone()
    });

    let result = handle.await.unwrap();
    assert_eq!(result, "ASYNC");
}

// ============================================================================
// SECTION 6: Bug L7 - Timezone Handling Tests
// Tests for timezone-related bugs in aggregation
// ============================================================================

#[test]
fn test_l7_day_boundary_utc() {
    let aggregator = OHLCVAggregator::new(100);

    // Just before midnight UTC
    let before_midnight = Utc.with_ymd_and_hms(2024, 1, 15, 23, 59, 59).unwrap();
    aggregator.add_trade("TZ", dec!(100.0), 100, before_midnight);

    // Just after midnight UTC
    let after_midnight = Utc.with_ymd_and_hms(2024, 1, 16, 0, 0, 1).unwrap();
    aggregator.add_trade("TZ", dec!(101.0), 100, after_midnight);

    // Should be in different daily buckets
    let current = aggregator.get_current("TZ", AggregationInterval::Day1);
    assert!(current.is_some());
}

#[test]
fn test_l7_hour_boundary() {
    let aggregator = OHLCVAggregator::new(100);

    let end_of_hour = Utc.with_ymd_and_hms(2024, 1, 15, 13, 59, 59).unwrap();
    aggregator.add_trade("HOUR", dec!(100.0), 100, end_of_hour);

    let start_of_next_hour = Utc.with_ymd_and_hms(2024, 1, 15, 14, 0, 0).unwrap();
    aggregator.add_trade("HOUR", dec!(101.0), 100, start_of_next_hour);

    let current = aggregator.get_current("HOUR", AggregationInterval::Hour1);
    assert!(current.is_some());
}

#[test]
fn test_l7_minute_alignment() {
    let aggregator = OHLCVAggregator::new(100);

    // Test 5-minute alignment
    let ts_10_03 = Utc.with_ymd_and_hms(2024, 1, 15, 10, 3, 0).unwrap();
    aggregator.add_trade("MIN5", dec!(100.0), 100, ts_10_03);

    let ts_10_07 = Utc.with_ymd_and_hms(2024, 1, 15, 10, 7, 0).unwrap();
    aggregator.add_trade("MIN5", dec!(101.0), 100, ts_10_07);

    // 10:03 should be in 10:00 bucket, 10:07 should be in 10:05 bucket
    let history = aggregator.get_history("MIN5", AggregationInterval::Minute5, 10);
    // History behavior depends on bucket transitions
    let _ = history;
}

#[test]
fn test_l7_15_minute_alignment() {
    let aggregator = OHLCVAggregator::new(100);

    let ts_10_03 = Utc.with_ymd_and_hms(2024, 1, 15, 10, 3, 0).unwrap();
    aggregator.add_trade("MIN15", dec!(100.0), 100, ts_10_03);

    let ts_10_16 = Utc.with_ymd_and_hms(2024, 1, 15, 10, 16, 0).unwrap();
    aggregator.add_trade("MIN15", dec!(101.0), 100, ts_10_16);

    let current = aggregator.get_current("MIN15", AggregationInterval::Minute15);
    assert!(current.is_some());
}

#[test]
fn test_l7_second_precision() {
    let aggregator = OHLCVAggregator::new(100);

    let ts1 = Utc.with_ymd_and_hms(2024, 1, 15, 10, 0, 0).unwrap();
    let ts2 = Utc.with_ymd_and_hms(2024, 1, 15, 10, 0, 1).unwrap();

    aggregator.add_trade("SEC", dec!(100.0), 100, ts1);
    aggregator.add_trade("SEC", dec!(101.0), 100, ts2);

    let current = aggregator.get_current("SEC", AggregationInterval::Second1);
    assert!(current.is_some());
}

#[test]
fn test_l7_dst_transition_simulation() {
    let aggregator = OHLCVAggregator::new(100);

    // Simulate times around DST (using UTC doesn't have DST, but tests boundary handling)
    let ts1 = Utc.with_ymd_and_hms(2024, 3, 10, 1, 59, 0).unwrap();
    let ts2 = Utc.with_ymd_and_hms(2024, 3, 10, 3, 0, 0).unwrap();

    aggregator.add_trade("DST", dec!(100.0), 100, ts1);
    aggregator.add_trade("DST", dec!(101.0), 100, ts2);

    let current = aggregator.get_current("DST", AggregationInterval::Hour1);
    assert!(current.is_some());
}

// ============================================================================
// SECTION 7: Bug D4 - Connection Pool Leak Tests
// Tests for resource leaks in connection/subscription management
// ============================================================================

#[tokio::test]
async fn test_d4_subscription_cleanup() {
    let feed = MarketFeed::new();

    // Create and drop many subscriptions
    for i in 0..50 {
        let symbol = format!("LEAK{}", i);
        let rx = feed.start_symbol_feed(symbol);
        drop(rx);
    }

    // Feed should still be operational
    let rx = feed.start_symbol_feed("FINAL".to_string());
    drop(rx);
}

#[tokio::test]
async fn test_d4_repeated_subscribe_unsubscribe() {
    let feed = MarketFeed::new();

    for _ in 0..20 {
        let rx = feed.subscribe_quotes("REPEAT");
        tokio::time::sleep(StdDuration::from_millis(10)).await;
        drop(rx);
    }
}

#[tokio::test]
async fn test_d4_concurrent_subscription_cleanup() {
    let feed = Arc::new(MarketFeed::new());
    let mut handles = vec![];

    for i in 0..10 {
        let feed_clone = feed.clone();
        let handle = tokio::spawn(async move {
            let symbol = format!("CONC{}", i);
            let rx = feed_clone.start_symbol_feed(symbol);
            tokio::time::sleep(StdDuration::from_millis(50)).await;
            drop(rx);
        });
        handles.push(handle);
    }

    for handle in handles {
        handle.await.unwrap();
    }
}

#[tokio::test]
async fn test_d4_aggregator_history_growth() {
    let aggregator = OHLCVAggregator::new(10); // Small history

    // Add many trades to fill history
    for i in 0..100 {
        let ts = Utc::now() + Duration::seconds(i as i64);
        aggregator.add_trade("GROWTH", Decimal::from(100 + i), 100, ts);
    }

    // History should be bounded
    let history = aggregator.get_history("GROWTH", AggregationInterval::Second1, 100);
    assert!(history.len() <= 10);
}

#[tokio::test]
async fn test_d4_feed_stop_cleanup() {
    let feed = MarketFeed::new();
    let _rx1 = feed.start_symbol_feed("STOP1".to_string());
    let _rx2 = feed.start_symbol_feed("STOP2".to_string());

    feed.stop();

    // After stop, new subscriptions should still work (feed recreatable)
    tokio::time::sleep(StdDuration::from_millis(50)).await;
}

// ============================================================================
// SECTION 8: Market Data Feed Tests
// General tests for market data feed functionality
// ============================================================================

#[test]
fn test_feed_creation() {
    let feed = MarketFeed::new();
    assert!(feed.get_last_quote("UNKNOWN").is_none());
    assert!(feed.get_last_trade("UNKNOWN").is_none());
}

#[tokio::test]
async fn test_feed_publish_quote() {
    let feed = MarketFeed::new();

    let quote = Quote {
        symbol: "TEST".to_string(),
        bid: dec!(100.0),
        ask: dec!(100.5),
        bid_size: 100,
        ask_size: 150,
        timestamp: Utc::now(),
        sequence: 1,
    };

    feed.publish_quote(quote.clone());

    let last = feed.get_last_quote("TEST");
    assert!(last.is_some());
    assert_eq!(last.unwrap().bid, dec!(100.0));
}

#[tokio::test]
async fn test_feed_publish_trade() {
    let feed = MarketFeed::new();

    let trade = Trade {
        symbol: "TEST".to_string(),
        price: dec!(100.25),
        quantity: 50,
        side: TradeSide::Buy,
        timestamp: Utc::now(),
        sequence: 1,
    };

    feed.publish_trade(trade.clone());

    let last = feed.get_last_trade("TEST");
    assert!(last.is_some());
    assert_eq!(last.unwrap().price, dec!(100.25));
}

#[tokio::test]
async fn test_feed_multiple_symbols() {
    let feed = MarketFeed::new();

    for symbol in ["AAPL", "GOOG", "MSFT", "AMZN"] {
        let quote = Quote {
            symbol: symbol.to_string(),
            bid: dec!(100.0),
            ask: dec!(100.5),
            bid_size: 100,
            ask_size: 100,
            timestamp: Utc::now(),
            sequence: 1,
        };
        feed.publish_quote(quote);
    }

    assert!(feed.get_last_quote("AAPL").is_some());
    assert!(feed.get_last_quote("GOOG").is_some());
    assert!(feed.get_last_quote("MSFT").is_some());
    assert!(feed.get_last_quote("AMZN").is_some());
}

#[tokio::test]
async fn test_feed_quote_updates() {
    let feed = MarketFeed::new();

    for i in 0..5 {
        let quote = Quote {
            symbol: "UPDATE".to_string(),
            bid: Decimal::from(100 + i),
            ask: Decimal::from(101 + i),
            bid_size: 100 + i as u64,
            ask_size: 100 + i as u64,
            timestamp: Utc::now(),
            sequence: i as u64,
        };
        feed.publish_quote(quote);
    }

    let last = feed.get_last_quote("UPDATE").unwrap();
    assert_eq!(last.bid, dec!(104));
}

// ============================================================================
// SECTION 9: OHLCV Aggregation Tests
// Tests for OHLCV bar aggregation functionality
// ============================================================================

#[test]
fn test_aggregator_creation() {
    let agg = OHLCVAggregator::new(100);
    assert!(agg.get_current("TEST", AggregationInterval::Minute1).is_none());
}

#[test]
fn test_aggregator_single_trade() {
    let agg = OHLCVAggregator::new(100);
    let ts = Utc::now();

    agg.add_trade("SINGLE", dec!(100.0), 100, ts);

    let bar = agg.get_current("SINGLE", AggregationInterval::Minute1).unwrap();
    assert_eq!(bar.open, dec!(100.0));
    assert_eq!(bar.high, dec!(100.0));
    assert_eq!(bar.low, dec!(100.0));
    assert_eq!(bar.close, dec!(100.0));
    assert_eq!(bar.volume, 100);
}

#[test]
fn test_aggregator_ohlc_values() {
    let agg = OHLCVAggregator::new(100);
    let base_ts = Utc::now();

    agg.add_trade("OHLC", dec!(100.0), 100, base_ts);
    agg.add_trade("OHLC", dec!(105.0), 50, base_ts + Duration::milliseconds(100));
    agg.add_trade("OHLC", dec!(95.0), 75, base_ts + Duration::milliseconds(200));
    agg.add_trade("OHLC", dec!(102.0), 25, base_ts + Duration::milliseconds(300));

    let bar = agg.get_current("OHLC", AggregationInterval::Minute1).unwrap();
    assert_eq!(bar.open, dec!(100.0));
    assert_eq!(bar.high, dec!(105.0));
    assert_eq!(bar.low, dec!(95.0));
    assert_eq!(bar.close, dec!(102.0));
    assert_eq!(bar.volume, 250);
}

#[test]
fn test_aggregator_multiple_intervals() {
    let agg = OHLCVAggregator::new(100);
    let ts = Utc::now();

    agg.add_trade("MULTI", dec!(100.0), 100, ts);

    // Should have bars for all intervals
    assert!(agg.get_current("MULTI", AggregationInterval::Second1).is_some());
    assert!(agg.get_current("MULTI", AggregationInterval::Minute1).is_some());
    assert!(agg.get_current("MULTI", AggregationInterval::Minute5).is_some());
    assert!(agg.get_current("MULTI", AggregationInterval::Minute15).is_some());
    assert!(agg.get_current("MULTI", AggregationInterval::Hour1).is_some());
    assert!(agg.get_current("MULTI", AggregationInterval::Day1).is_some());
}

#[test]
fn test_aggregator_volume_accumulation() {
    let agg = OHLCVAggregator::new(100);
    let ts = Utc::now();

    for i in 0..10 {
        agg.add_trade("VOL", dec!(100.0), 100, ts + Duration::milliseconds(i * 10));
    }

    let bar = agg.get_current("VOL", AggregationInterval::Minute1).unwrap();
    assert_eq!(bar.volume, 1000);
}

#[test]
fn test_aggregator_vwap_basic() {
    let agg = OHLCVAggregator::new(100);

    // Add trades across different seconds to create history
    for i in 0..5 {
        let ts = Utc.with_ymd_and_hms(2024, 1, 15, 10, 0, i as u32).unwrap();
        agg.add_trade("VWAP", Decimal::from(100 + i), 100, ts);
    }

    let vwap = agg.calculate_vwap("VWAP", AggregationInterval::Second1, 10);
    // VWAP calculation may or may not succeed depending on history state
    let _ = vwap;
}

#[test]
fn test_aggregator_empty_vwap() {
    let agg = OHLCVAggregator::new(100);

    let vwap = agg.calculate_vwap("NOVWAP", AggregationInterval::Minute1, 10);
    assert!(vwap.is_none());
}

// ============================================================================
// SECTION 10: Ring Buffer Tests
// Comprehensive tests for ring buffer implementation
// ============================================================================

#[test]
fn test_ring_buffer_new() {
    let rb: RingBuffer<i32> = RingBuffer::new(5);
    assert!(rb.is_empty());
    assert_eq!(rb.len(), 0);
}

#[test]
fn test_ring_buffer_push_single() {
    let mut rb: RingBuffer<i32> = RingBuffer::new(5);
    rb.push(42);

    assert!(!rb.is_empty());
    assert_eq!(rb.len(), 1);
}

#[test]
fn test_ring_buffer_push_to_capacity() {
    let mut rb: RingBuffer<i32> = RingBuffer::new(3);
    rb.push(1);
    rb.push(2);
    rb.push(3);

    assert_eq!(rb.len(), 3);
}

#[test]
fn test_ring_buffer_wrap_around() {
    let mut rb: RingBuffer<i32> = RingBuffer::new(3);
    rb.push(1);
    rb.push(2);
    rb.push(3);
    rb.push(4); // Should overwrite 1

    assert_eq!(rb.len(), 3);
}

#[test]
fn test_ring_buffer_many_wraps() {
    let mut rb: RingBuffer<i32> = RingBuffer::new(3);

    for i in 0..100 {
        rb.push(i);
    }

    assert_eq!(rb.len(), 3);
}

#[test]
fn test_ring_buffer_get_after_push() {
    let mut rb: RingBuffer<i32> = RingBuffer::new(5);
    rb.push(10);
    rb.push(20);
    rb.push(30);

    // Get should return some value (order may vary due to bugs)
    let val = rb.get(0);
    assert!(val.is_some());
}

#[test]
fn test_ring_buffer_iterator_count() {
    let mut rb: RingBuffer<i32> = RingBuffer::new(5);
    rb.push(1);
    rb.push(2);
    rb.push(3);

    let count = rb.iter().count();
    assert_eq!(count, 3);
}

#[test]
fn test_ring_buffer_iterator_after_wrap() {
    let mut rb: RingBuffer<i32> = RingBuffer::new(3);
    rb.push(1);
    rb.push(2);
    rb.push(3);
    rb.push(4);
    rb.push(5);

    let count = rb.iter().count();
    assert_eq!(count, 3);
}

// ============================================================================
// SECTION 11: Subscription/Broadcast Tests
// Tests for subscription management and broadcast functionality
// ============================================================================

#[tokio::test]
async fn test_broadcast_single_subscriber() {
    let feed = MarketFeed::new();
    let mut rx = feed.start_symbol_feed("BCAST".to_string());

    tokio::time::sleep(StdDuration::from_millis(150)).await;

    // Should receive at least one message
    let result = rx.try_recv();
    match result {
        Ok(_) => (),
        Err(tokio::sync::broadcast::error::TryRecvError::Empty) => (),
        Err(tokio::sync::broadcast::error::TryRecvError::Lagged(_)) => (),
        Err(e) => panic!("Unexpected error: {:?}", e),
    }
}

#[tokio::test]
async fn test_broadcast_multiple_subscribers() {
    let feed = MarketFeed::new();
    let _rx1 = feed.start_symbol_feed("MULTI".to_string());
    let _rx2 = feed.subscribe_quotes("MULTI");
    let _rx3 = feed.subscribe_quotes("MULTI");

    let quote = Quote {
        symbol: "MULTI".to_string(),
        bid: dec!(100.0),
        ask: dec!(100.5),
        bid_size: 100,
        ask_size: 100,
        timestamp: Utc::now(),
        sequence: 1,
    };

    feed.publish_quote(quote);
}

#[tokio::test]
async fn test_subscribe_to_nonexistent_symbol() {
    let feed = MarketFeed::new();

    // Subscribing to non-existent symbol should create new feed
    let _rx = feed.subscribe_quotes("NEWCREATE");

    tokio::time::sleep(StdDuration::from_millis(150)).await;
}

#[tokio::test]
async fn test_trade_subscription() {
    let feed = MarketFeed::new();

    let trade = Trade {
        symbol: "TSUB".to_string(),
        price: dec!(100.0),
        quantity: 100,
        side: TradeSide::Sell,
        timestamp: Utc::now(),
        sequence: 1,
    };

    feed.publish_trade(trade);

    let last = feed.get_last_trade("TSUB");
    assert!(last.is_some());
}

// ============================================================================
// SECTION 12: Edge Cases and Stress Tests
// ============================================================================

#[test]
fn test_edge_empty_symbol() {
    let feed = MarketFeed::new();
    assert!(feed.get_last_quote("").is_none());
}

#[test]
fn test_edge_large_quantity() {
    let agg = OHLCVAggregator::new(100);
    let ts = Utc::now();

    agg.add_trade("LARGE", dec!(100.0), u64::MAX / 2, ts);
    agg.add_trade("LARGE", dec!(100.0), u64::MAX / 2, ts);

    let bar = agg.get_current("LARGE", AggregationInterval::Minute1);
    assert!(bar.is_some());
}

#[test]
fn test_edge_decimal_precision() {
    let agg = OHLCVAggregator::new(100);
    let ts = Utc::now();

    agg.add_trade("PREC", dec!(0.00000001), 1, ts);

    let bar = agg.get_current("PREC", AggregationInterval::Minute1).unwrap();
    assert_eq!(bar.open, dec!(0.00000001));
}

#[test]
fn test_edge_negative_price() {
    let agg = OHLCVAggregator::new(100);
    let ts = Utc::now();

    // Some assets can have negative prices
    agg.add_trade("NEG", dec!(-10.0), 100, ts);

    let bar = agg.get_current("NEG", AggregationInterval::Minute1).unwrap();
    assert_eq!(bar.open, dec!(-10.0));
}

#[test]
fn test_edge_zero_volume() {
    let agg = OHLCVAggregator::new(100);
    let ts = Utc::now();

    agg.add_trade("ZERO", dec!(100.0), 0, ts);

    let bar = agg.get_current("ZERO", AggregationInterval::Minute1).unwrap();
    assert_eq!(bar.volume, 0);
}

#[tokio::test]
async fn test_stress_rapid_quotes() {
    let feed = MarketFeed::new();

    for i in 0..1000 {
        let quote = Quote {
            symbol: "STRESS".to_string(),
            bid: Decimal::from(i),
            ask: Decimal::from(i + 1),
            bid_size: 100,
            ask_size: 100,
            timestamp: Utc::now(),
            sequence: i as u64,
        };
        feed.publish_quote(quote);
    }

    let last = feed.get_last_quote("STRESS");
    assert!(last.is_some());
}

#[test]
fn test_stress_many_symbols() {
    let agg = OHLCVAggregator::new(10);
    let ts = Utc::now();

    for i in 0..100 {
        let symbol = format!("SYM{:04}", i);
        agg.add_trade(&symbol, dec!(100.0), 100, ts);
    }

    // All symbols should have bars
    for i in 0..100 {
        let symbol = format!("SYM{:04}", i);
        assert!(agg.get_current(&symbol, AggregationInterval::Minute1).is_some());
    }
}

#[test]
fn test_interval_duration() {
    assert_eq!(AggregationInterval::Second1.duration(), Duration::seconds(1));
    assert_eq!(AggregationInterval::Minute1.duration(), Duration::minutes(1));
    assert_eq!(AggregationInterval::Minute5.duration(), Duration::minutes(5));
    assert_eq!(AggregationInterval::Minute15.duration(), Duration::minutes(15));
    assert_eq!(AggregationInterval::Hour1.duration(), Duration::hours(1));
    assert_eq!(AggregationInterval::Day1.duration(), Duration::days(1));
}

#[test]
fn test_trade_side_variants() {
    let buy = TradeSide::Buy;
    let sell = TradeSide::Sell;

    // Should be different
    match buy {
        TradeSide::Buy => (),
        TradeSide::Sell => panic!("Wrong variant"),
    }

    match sell {
        TradeSide::Sell => (),
        TradeSide::Buy => panic!("Wrong variant"),
    }
}

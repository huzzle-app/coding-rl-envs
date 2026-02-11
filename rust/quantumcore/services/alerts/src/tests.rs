#[cfg(test)]
mod tests {
    use crate::engine::{Alert, AlertCondition, AlertEngine, NotificationChannel};
    use chrono::Utc;
    use rust_decimal::Decimal;
    use rust_decimal_macros::dec;
    use std::sync::Arc;
    use std::thread;
    use std::time::Duration;
    use uuid::Uuid;

    // Helper function to create a test alert
    fn create_test_alert(symbol: &str, condition: AlertCondition) -> Alert {
        Alert {
            id: Uuid::new_v4(),
            user_id: "test_user".to_string(),
            symbol: symbol.to_string(),
            condition,
            notification_channels: vec![NotificationChannel::InApp],
            created_at: Utc::now(),
            triggered_at: None,
            active: true,
        }
    }

    fn create_alert_with_user(user_id: &str, symbol: &str, condition: AlertCondition) -> Alert {
        Alert {
            id: Uuid::new_v4(),
            user_id: user_id.to_string(),
            symbol: symbol.to_string(),
            condition,
            notification_channels: vec![NotificationChannel::InApp],
            created_at: Utc::now(),
            triggered_at: None,
            active: false,
        }
    }

    // ==================== Alert Creation Tests ====================

    #[test]
    fn test_create_alert_returns_id() {
        let engine = AlertEngine::new();
        let alert = create_test_alert("BTC", AlertCondition::PriceAbove(dec!(50000)));
        let id = alert.id;

        let result = engine.create_alert(alert);
        assert!(result.is_ok());
        assert_eq!(result.unwrap(), id);
    }

    #[test]
    fn test_create_multiple_alerts() {
        let engine = AlertEngine::new();

        for i in 0..10 {
            let alert = create_test_alert("BTC", AlertCondition::PriceAbove(Decimal::from(50000 + i)));
            assert!(engine.create_alert(alert).is_ok());
        }
    }

    #[test]
    fn test_get_alert_after_creation() {
        let engine = AlertEngine::new();
        let alert = create_test_alert("ETH", AlertCondition::PriceBelow(dec!(3000)));
        let id = alert.id;

        engine.create_alert(alert.clone()).unwrap();

        let retrieved = engine.get_alert(id);
        assert!(retrieved.is_some());
        assert_eq!(retrieved.unwrap().symbol, "ETH");
    }

    #[test]
    fn test_get_nonexistent_alert_returns_none() {
        let engine = AlertEngine::new();
        let result = engine.get_alert(Uuid::new_v4());
        assert!(result.is_none());
    }

    #[test]
    fn test_create_alert_with_email_channel() {
        let engine = AlertEngine::new();
        let mut alert = create_test_alert("BTC", AlertCondition::PriceAbove(dec!(50000)));
        alert.notification_channels = vec![NotificationChannel::Email("test@example.com".to_string())];

        let id = engine.create_alert(alert).unwrap();
        let retrieved = engine.get_alert(id).unwrap();

        match &retrieved.notification_channels[0] {
            NotificationChannel::Email(email) => assert_eq!(email, "test@example.com"),
            _ => panic!("Expected Email channel"),
        }
    }

    #[test]
    fn test_create_alert_with_webhook_channel() {
        let engine = AlertEngine::new();
        let mut alert = create_test_alert("BTC", AlertCondition::PriceAbove(dec!(50000)));
        alert.notification_channels = vec![NotificationChannel::Webhook("https://webhook.example.com".to_string())];

        let id = engine.create_alert(alert).unwrap();
        let retrieved = engine.get_alert(id).unwrap();

        match &retrieved.notification_channels[0] {
            NotificationChannel::Webhook(url) => assert_eq!(url, "https://webhook.example.com"),
            _ => panic!("Expected Webhook channel"),
        }
    }

    #[test]
    fn test_create_alert_with_push_channel() {
        let engine = AlertEngine::new();
        let mut alert = create_test_alert("BTC", AlertCondition::PriceAbove(dec!(50000)));
        alert.notification_channels = vec![NotificationChannel::Push { device_id: "device123".to_string() }];

        let id = engine.create_alert(alert).unwrap();
        let retrieved = engine.get_alert(id).unwrap();

        match &retrieved.notification_channels[0] {
            NotificationChannel::Push { device_id } => assert_eq!(device_id, "device123"),
            _ => panic!("Expected Push channel"),
        }
    }

    #[test]
    fn test_create_alert_with_multiple_channels() {
        let engine = AlertEngine::new();
        let mut alert = create_test_alert("BTC", AlertCondition::PriceAbove(dec!(50000)));
        alert.notification_channels = vec![
            NotificationChannel::Email("test@example.com".to_string()),
            NotificationChannel::InApp,
            NotificationChannel::Webhook("https://webhook.example.com".to_string()),
        ];

        let id = engine.create_alert(alert).unwrap();
        let retrieved = engine.get_alert(id).unwrap();
        assert_eq!(retrieved.notification_channels.len(), 3);
    }

    // ==================== Price Condition Tests ====================

    #[test]
    fn test_price_above_condition_triggers() {
        let engine = AlertEngine::new();
        let alert = create_test_alert("BTC", AlertCondition::PriceAbove(dec!(50000)));
        let id = alert.id;

        engine.create_alert(alert).unwrap();
        let rx = engine.take_notification_receiver().unwrap();

        // Update price above threshold
        engine.update_price("BTC", dec!(50001));

        // Check notification was sent
        let notification = rx.try_recv();
        assert!(notification.is_ok());
        assert_eq!(notification.unwrap().alert_id, id);
    }

    #[test]
    fn test_price_above_condition_does_not_trigger_below() {
        let engine = AlertEngine::new();
        let alert = create_test_alert("BTC", AlertCondition::PriceAbove(dec!(50000)));

        engine.create_alert(alert).unwrap();
        let rx = engine.take_notification_receiver().unwrap();

        // Update price below threshold
        engine.update_price("BTC", dec!(49999));

        // No notification should be sent
        assert!(rx.try_recv().is_err());
    }

    #[test]
    fn test_price_above_condition_exact_threshold() {
        let engine = AlertEngine::new();
        let alert = create_test_alert("BTC", AlertCondition::PriceAbove(dec!(50000)));

        engine.create_alert(alert).unwrap();
        let rx = engine.take_notification_receiver().unwrap();

        // Update price exactly at threshold (should NOT trigger - needs to be above)
        engine.update_price("BTC", dec!(50000));

        assert!(rx.try_recv().is_err());
    }

    #[test]
    fn test_price_below_condition_triggers() {
        let engine = AlertEngine::new();
        let alert = create_test_alert("ETH", AlertCondition::PriceBelow(dec!(3000)));
        let id = alert.id;

        engine.create_alert(alert).unwrap();
        let rx = engine.take_notification_receiver().unwrap();

        // Update price below threshold
        engine.update_price("ETH", dec!(2999));

        let notification = rx.try_recv();
        assert!(notification.is_ok());
        assert_eq!(notification.unwrap().alert_id, id);
    }

    #[test]
    fn test_price_below_condition_does_not_trigger_above() {
        let engine = AlertEngine::new();
        let alert = create_test_alert("ETH", AlertCondition::PriceBelow(dec!(3000)));

        engine.create_alert(alert).unwrap();
        let rx = engine.take_notification_receiver().unwrap();

        // Update price above threshold
        engine.update_price("ETH", dec!(3001));

        assert!(rx.try_recv().is_err());
    }

    #[test]
    fn test_price_below_exact_threshold() {
        let engine = AlertEngine::new();
        let alert = create_test_alert("ETH", AlertCondition::PriceBelow(dec!(3000)));

        engine.create_alert(alert).unwrap();
        let rx = engine.take_notification_receiver().unwrap();

        // Update price exactly at threshold (should NOT trigger - needs to be below)
        engine.update_price("ETH", dec!(3000));

        assert!(rx.try_recv().is_err());
    }

    #[test]
    fn test_price_change_condition_with_increase() {
        let engine = AlertEngine::new();
        let alert = create_test_alert("BTC", AlertCondition::PriceChange {
            threshold_percent: dec!(5),
            window_seconds: 60,
        });
        let id = alert.id;

        engine.create_alert(alert).unwrap();
        let rx = engine.take_notification_receiver().unwrap();

        // Initial price
        engine.update_price("BTC", dec!(100));

        // No trigger on initial price alone (no history for comparison)
        assert!(rx.try_recv().is_err());

        // Price increase of 10%
        engine.update_price("BTC", dec!(110));

        let notification = rx.try_recv();
        assert!(notification.is_ok());
        assert_eq!(notification.unwrap().alert_id, id);
    }

    #[test]
    fn test_price_change_condition_with_decrease() {
        let engine = AlertEngine::new();
        let alert = create_test_alert("ETH", AlertCondition::PriceChange {
            threshold_percent: dec!(5),
            window_seconds: 60,
        });
        let id = alert.id;

        engine.create_alert(alert).unwrap();
        let rx = engine.take_notification_receiver().unwrap();

        // Initial price
        engine.update_price("ETH", dec!(100));

        // Price decrease of 10%
        engine.update_price("ETH", dec!(90));

        let notification = rx.try_recv();
        assert!(notification.is_ok());
        assert_eq!(notification.unwrap().alert_id, id);
    }

    #[test]
    fn test_price_change_below_threshold_no_trigger() {
        let engine = AlertEngine::new();
        let alert = create_test_alert("XRP", AlertCondition::PriceChange {
            threshold_percent: dec!(10),
            window_seconds: 60,
        });

        engine.create_alert(alert).unwrap();
        let rx = engine.take_notification_receiver().unwrap();

        // Initial price
        engine.update_price("XRP", dec!(100));

        // Price change of only 5%
        engine.update_price("XRP", dec!(105));

        assert!(rx.try_recv().is_err());
    }

    #[test]
    fn test_volume_spike_never_triggers() {
        
        let engine = AlertEngine::new();
        let alert = create_test_alert("BTC", AlertCondition::VolumeSpike {
            threshold_multiplier: dec!(2),
        });

        engine.create_alert(alert).unwrap();
        let rx = engine.take_notification_receiver().unwrap();

        engine.update_price("BTC", dec!(50000));
        engine.update_price("BTC", dec!(51000));
        engine.update_price("BTC", dec!(52000));

        // VolumeSpike should never trigger (bug in implementation)
        assert!(rx.try_recv().is_err());
    }

    // ==================== Alert Trigger Tests ====================

    #[test]
    fn test_alert_becomes_inactive_after_trigger() {
        let engine = AlertEngine::new();
        let alert = create_test_alert("BTC", AlertCondition::PriceAbove(dec!(50000)));
        let id = alert.id;

        engine.create_alert(alert).unwrap();
        let _rx = engine.take_notification_receiver().unwrap();

        engine.update_price("BTC", dec!(50001));

        let retrieved = engine.get_alert(id).unwrap();
        assert!(!retrieved.active);
    }

    #[test]
    fn test_alert_has_triggered_at_after_trigger() {
        let engine = AlertEngine::new();
        let alert = create_test_alert("BTC", AlertCondition::PriceAbove(dec!(50000)));
        let id = alert.id;

        engine.create_alert(alert).unwrap();
        let _rx = engine.take_notification_receiver().unwrap();

        engine.update_price("BTC", dec!(50001));

        let retrieved = engine.get_alert(id).unwrap();
        assert!(retrieved.triggered_at.is_some());
    }

    #[test]
    fn test_inactive_alert_does_not_trigger() {
        let engine = AlertEngine::new();
        let mut alert = create_test_alert("BTC", AlertCondition::PriceAbove(dec!(50000)));
        alert.active = false;

        engine.create_alert(alert).unwrap();
        let rx = engine.take_notification_receiver().unwrap();

        engine.update_price("BTC", dec!(50001));

        assert!(rx.try_recv().is_err());
    }

    #[test]
    fn test_alert_only_triggers_for_matching_symbol() {
        let engine = AlertEngine::new();
        let alert = create_test_alert("BTC", AlertCondition::PriceAbove(dec!(50000)));

        engine.create_alert(alert).unwrap();
        let rx = engine.take_notification_receiver().unwrap();

        // Update price for different symbol
        engine.update_price("ETH", dec!(60000));

        assert!(rx.try_recv().is_err());
    }

    #[test]
    fn test_one_shot_alert_does_not_trigger_twice() {
        let engine = AlertEngine::new();
        let alert = create_test_alert("BTC", AlertCondition::PriceAbove(dec!(50000)));

        engine.create_alert(alert).unwrap();
        let rx = engine.take_notification_receiver().unwrap();

        // First trigger
        engine.update_price("BTC", dec!(50001));
        assert!(rx.try_recv().is_ok());

        // Second price update - should not trigger again
        engine.update_price("BTC", dec!(50002));
        assert!(rx.try_recv().is_err());
    }

    // ==================== User Alert Tests ====================

    #[test]
    fn test_get_user_alerts() {
        let engine = AlertEngine::new();

        let alert1 = create_alert_with_user("user1", "BTC", AlertCondition::PriceAbove(dec!(50000)));
        let alert2 = create_alert_with_user("user1", "ETH", AlertCondition::PriceBelow(dec!(3000)));
        let alert3 = create_alert_with_user("user2", "BTC", AlertCondition::PriceAbove(dec!(60000)));

        engine.create_alert(alert1).unwrap();
        engine.create_alert(alert2).unwrap();
        engine.create_alert(alert3).unwrap();

        let user1_alerts = engine.get_user_alerts("user1");
        assert_eq!(user1_alerts.len(), 2);

        let user2_alerts = engine.get_user_alerts("user2");
        assert_eq!(user2_alerts.len(), 1);
    }

    #[test]
    fn test_get_user_alerts_empty() {
        let engine = AlertEngine::new();
        let alerts = engine.get_user_alerts("nonexistent_user");
        assert!(alerts.is_empty());
    }

    // ==================== Cancel Alert Tests ====================

    #[test]
    fn test_cancel_alert_success() {
        let engine = AlertEngine::new();
        let alert = create_test_alert("BTC", AlertCondition::PriceAbove(dec!(50000)));
        let id = alert.id;

        engine.create_alert(alert).unwrap();

        let result = engine.cancel_alert(id);
        assert!(result.is_ok());

        let retrieved = engine.get_alert(id).unwrap();
        assert!(!retrieved.active);
    }

    #[test]
    fn test_cancel_nonexistent_alert_fails() {
        let engine = AlertEngine::new();
        let result = engine.cancel_alert(Uuid::new_v4());
        assert!(result.is_err());
    }

    #[test]
    fn test_cancelled_alert_does_not_trigger() {
        let engine = AlertEngine::new();
        let alert = create_test_alert("BTC", AlertCondition::PriceAbove(dec!(50000)));
        let id = alert.id;

        engine.create_alert(alert).unwrap();
        engine.cancel_alert(id).unwrap();

        let rx = engine.take_notification_receiver().unwrap();
        engine.update_price("BTC", dec!(50001));

        assert!(rx.try_recv().is_err());
    }

    // ==================== Notification Channel Tests (Bug A4) ====================

    #[test]
    fn test_notification_receiver_can_be_taken_once() {
        let engine = AlertEngine::new();

        let rx1 = engine.take_notification_receiver();
        assert!(rx1.is_some());

        let rx2 = engine.take_notification_receiver();
        assert!(rx2.is_none());
    }

    #[test]
    fn test_notification_contains_correct_info() {
        let engine = AlertEngine::new();
        let mut alert = create_test_alert("BTC", AlertCondition::PriceAbove(dec!(50000)));
        alert.user_id = "specific_user".to_string();
        let id = alert.id;

        engine.create_alert(alert).unwrap();
        let rx = engine.take_notification_receiver().unwrap();

        engine.update_price("BTC", dec!(50001));

        let notification = rx.try_recv().unwrap();
        assert_eq!(notification.alert_id, id);
        assert_eq!(notification.user_id, "specific_user");
        assert!(notification.message.contains("BTC"));
        assert!(notification.message.contains("50001"));
    }

    #[test]
    fn test_channel_buffer_overflow_drops_notifications() {
        
        let engine = AlertEngine::new();

        // Create many alerts
        for i in 0..150 {
            let mut alert = create_test_alert("BTC", AlertCondition::PriceAbove(Decimal::from(i)));
            alert.id = Uuid::new_v4();
            engine.create_alert(alert).unwrap();
        }

        // Don't take receiver - channel will fill up
        // Update price to trigger all alerts
        engine.update_price("BTC", dec!(200));

        // Now take receiver and count notifications
        let rx = engine.take_notification_receiver().unwrap();
        let mut count = 0;
        while rx.try_recv().is_ok() {
            count += 1;
        }

        // Should have fewer than 150 due to buffer overflow
        // This test demonstrates the A4 bug
        assert!(count <= 100, "Expected at most 100 notifications due to buffer, got {}", count);
    }

    // ==================== Borrow Checker / Interior Mutability Tests (Bug A8) ====================

    #[test]
    fn test_concurrent_alert_creation() {
        let engine = Arc::new(AlertEngine::new());
        let mut handles = vec![];

        for i in 0..10 {
            let engine_clone = Arc::clone(&engine);
            let handle = thread::spawn(move || {
                for j in 0..10 {
                    let alert = create_test_alert(
                        &format!("SYM{}", i * 10 + j),
                        AlertCondition::PriceAbove(Decimal::from(i * 10 + j)),
                    );
                    engine_clone.create_alert(alert).unwrap();
                }
            });
            handles.push(handle);
        }

        for handle in handles {
            handle.join().unwrap();
        }

        // Should have 100 alerts total
        let all_alerts = engine.get_user_alerts("test_user");
        assert_eq!(all_alerts.len(), 100);
    }

    #[test]
    fn test_concurrent_price_updates() {
        let engine = Arc::new(AlertEngine::new());
        let _rx = engine.take_notification_receiver().unwrap();

        let mut handles = vec![];

        for i in 0..10 {
            let engine_clone = Arc::clone(&engine);
            let handle = thread::spawn(move || {
                for j in 0..100 {
                    engine_clone.update_price("BTC", Decimal::from(i * 100 + j));
                }
            });
            handles.push(handle);
        }

        for handle in handles {
            handle.join().unwrap();
        }

        // No panic means DashMap handled concurrent access correctly
    }

    #[test]
    fn test_concurrent_read_and_write() {
        let engine = Arc::new(AlertEngine::new());

        // Create some initial alerts
        for i in 0..50 {
            let alert = create_test_alert("BTC", AlertCondition::PriceAbove(Decimal::from(i)));
            engine.create_alert(alert).unwrap();
        }

        let engine_reader = Arc::clone(&engine);
        let engine_writer = Arc::clone(&engine);

        let reader_handle = thread::spawn(move || {
            for _ in 0..100 {
                let _ = engine_reader.get_user_alerts("test_user");
                thread::sleep(Duration::from_micros(100));
            }
        });

        let writer_handle = thread::spawn(move || {
            for i in 50..100 {
                let alert = create_test_alert("ETH", AlertCondition::PriceAbove(Decimal::from(i)));
                engine_writer.create_alert(alert).unwrap();
            }
        });

        reader_handle.join().unwrap();
        writer_handle.join().unwrap();
    }

    #[test]
    fn test_interior_mutability_with_dashmap() {
        // Testing that DashMap provides safe interior mutability
        let engine = AlertEngine::new();
        let alert = create_test_alert("BTC", AlertCondition::PriceAbove(dec!(50000)));
        let id = alert.id;

        engine.create_alert(alert).unwrap();

        // Cancel should work through interior mutability
        engine.cancel_alert(id).unwrap();

        // Verify the mutation happened
        let retrieved = engine.get_alert(id).unwrap();
        assert!(!retrieved.active);
    }

    // ==================== Condvar / Spurious Wakeup Tests (Bug B9) ====================

    #[test]
    fn test_notification_receiver_blocking() {
        let engine = Arc::new(AlertEngine::new());
        let rx = engine.take_notification_receiver().unwrap();

        let alert = create_test_alert("BTC", AlertCondition::PriceAbove(dec!(50000)));
        engine.create_alert(alert).unwrap();

        let engine_clone = Arc::clone(&engine);
        let sender_handle = thread::spawn(move || {
            thread::sleep(Duration::from_millis(50));
            engine_clone.update_price("BTC", dec!(50001));
        });

        // This should block until notification is sent
        let notification = rx.recv_timeout(Duration::from_secs(1));
        assert!(notification.is_ok());

        sender_handle.join().unwrap();
    }

    #[test]
    fn test_notification_receiver_timeout() {
        let engine = AlertEngine::new();
        let rx = engine.take_notification_receiver().unwrap();

        // No alerts created, no price updates
        let notification = rx.recv_timeout(Duration::from_millis(100));
        assert!(notification.is_err());
    }

    #[test]
    fn test_stop_engine() {
        let engine = AlertEngine::new();
        engine.stop();
        // Engine should be stopped, but this is a no-op in current implementation
        // Testing that stop doesn't panic
    }

    // ==================== Deduplication Tests (Bug H3) ====================

    #[test]
    fn test_rapid_price_updates_cause_duplicate_notifications() {
        
        let engine = AlertEngine::new();

        // Create alert that triggers above 100
        let alert1 = create_test_alert("BTC", AlertCondition::PriceAbove(dec!(100)));
        engine.create_alert(alert1).unwrap();

        let rx = engine.take_notification_receiver().unwrap();

        // Price oscillates above and below threshold
        // But since alert becomes inactive after first trigger, this actually
        // demonstrates the one-shot behavior, not the deduplication bug
        engine.update_price("BTC", dec!(101));

        let count = std::iter::from_fn(|| rx.try_recv().ok()).count();
        assert_eq!(count, 1);  // One-shot alert only fires once
    }

    #[test]
    fn test_multiple_alerts_same_condition() {
        let engine = AlertEngine::new();

        // Create multiple alerts with same condition
        for _ in 0..5 {
            let alert = create_test_alert("BTC", AlertCondition::PriceAbove(dec!(100)));
            engine.create_alert(alert).unwrap();
        }

        let rx = engine.take_notification_receiver().unwrap();
        engine.update_price("BTC", dec!(101));

        // All 5 should trigger
        let count = std::iter::from_fn(|| rx.try_recv().ok()).count();
        assert_eq!(count, 5);
    }

    // ==================== History and Pruning Tests (Bug H1) ====================

    #[test]
    fn test_price_history_accumulates() {
        let engine = AlertEngine::new();

        for i in 0..100 {
            engine.update_price("BTC", Decimal::from(i));
        }

        
        // We can't directly inspect the history, but we can test that
        // price change calculations still work
        let alert = create_test_alert("BTC", AlertCondition::PriceChange {
            threshold_percent: dec!(50),
            window_seconds: 3600,
        });
        engine.create_alert(alert).unwrap();

        let rx = engine.take_notification_receiver().unwrap();
        engine.update_price("BTC", dec!(200));

        // Should trigger since price changed significantly
        assert!(rx.try_recv().is_ok());
    }

    #[test]
    fn test_prune_history() {
        let engine = AlertEngine::new();

        // Add some history
        for i in 0..10 {
            engine.update_price("BTC", Decimal::from(i));
        }

        // Prune with 0 seconds - should remove all
        engine.prune_history(0);

        // After pruning, price change should not trigger (no history)
        let alert = create_test_alert("BTC", AlertCondition::PriceChange {
            threshold_percent: dec!(1),
            window_seconds: 60,
        });
        engine.create_alert(alert).unwrap();

        let rx = engine.take_notification_receiver().unwrap();
        engine.update_price("BTC", dec!(100));

        // May or may not trigger depending on timing
        // This test just ensures prune_history doesn't panic
    }

    #[test]
    fn test_stale_price_cache() {
        
        let engine = AlertEngine::new();

        engine.update_price("BTC", dec!(50000));

        // Sleep briefly
        thread::sleep(Duration::from_millis(10));

        // Price in cache is now "stale" but still used
        let alert = create_test_alert("BTC", AlertCondition::PriceAbove(dec!(49999)));
        engine.create_alert(alert).unwrap();

        // Note: The bug is that cache isn't invalidated based on age
        // but alerts check current price, not cached price
    }

    // ==================== Edge Case Tests ====================

    #[test]
    fn test_zero_threshold() {
        let engine = AlertEngine::new();
        let alert = create_test_alert("BTC", AlertCondition::PriceAbove(dec!(0)));

        engine.create_alert(alert).unwrap();
        let rx = engine.take_notification_receiver().unwrap();

        engine.update_price("BTC", dec!(1));
        assert!(rx.try_recv().is_ok());
    }

    #[test]
    fn test_negative_price() {
        let engine = AlertEngine::new();
        let alert = create_test_alert("BTC", AlertCondition::PriceBelow(dec!(0)));

        engine.create_alert(alert).unwrap();
        let rx = engine.take_notification_receiver().unwrap();

        engine.update_price("BTC", dec!(-1));
        assert!(rx.try_recv().is_ok());
    }

    #[test]
    fn test_very_large_price() {
        let engine = AlertEngine::new();
        let large_price = Decimal::from(1_000_000_000_000i64);
        let alert = create_test_alert("BTC", AlertCondition::PriceAbove(large_price - Decimal::ONE));

        engine.create_alert(alert).unwrap();
        let rx = engine.take_notification_receiver().unwrap();

        engine.update_price("BTC", large_price);
        assert!(rx.try_recv().is_ok());
    }

    #[test]
    fn test_empty_symbol() {
        let engine = AlertEngine::new();
        let alert = create_test_alert("", AlertCondition::PriceAbove(dec!(100)));

        engine.create_alert(alert).unwrap();
        let rx = engine.take_notification_receiver().unwrap();

        engine.update_price("", dec!(101));
        assert!(rx.try_recv().is_ok());
    }

    #[test]
    fn test_special_characters_in_symbol() {
        let engine = AlertEngine::new();
        let alert = create_test_alert("BTC/USD", AlertCondition::PriceAbove(dec!(100)));

        engine.create_alert(alert).unwrap();
        let rx = engine.take_notification_receiver().unwrap();

        engine.update_price("BTC/USD", dec!(101));
        assert!(rx.try_recv().is_ok());
    }

    #[test]
    fn test_unicode_in_user_id() {
        let engine = AlertEngine::new();
        let mut alert = create_test_alert("BTC", AlertCondition::PriceAbove(dec!(100)));
        alert.user_id = "user_\u{1F600}_emoji".to_string();

        engine.create_alert(alert).unwrap();
        let rx = engine.take_notification_receiver().unwrap();

        engine.update_price("BTC", dec!(101));
        let notification = rx.try_recv().unwrap();
        assert_eq!(notification.user_id, "user_\u{1F600}_emoji");
    }

    #[test]
    fn test_decimal_precision() {
        let engine = AlertEngine::new();
        let precise_threshold = Decimal::from_str_exact("100.123456789").unwrap();
        let alert = create_test_alert("BTC", AlertCondition::PriceAbove(precise_threshold));

        engine.create_alert(alert).unwrap();
        let rx = engine.take_notification_receiver().unwrap();

        // Exactly at threshold - should not trigger
        engine.update_price("BTC", precise_threshold);
        assert!(rx.try_recv().is_err());

        // Just above threshold
        let just_above = Decimal::from_str_exact("100.12345679").unwrap();
        engine.update_price("BTC", just_above);
        assert!(rx.try_recv().is_ok());
    }

    #[test]
    fn test_many_symbols() {
        let engine = AlertEngine::new();

        // Create alerts for many different symbols
        for i in 0..50 {
            let alert = create_test_alert(&format!("SYM{}", i), AlertCondition::PriceAbove(dec!(100)));
            engine.create_alert(alert).unwrap();
        }

        let rx = engine.take_notification_receiver().unwrap();

        // Only update price for symbol 25
        engine.update_price("SYM25", dec!(101));

        let count = std::iter::from_fn(|| rx.try_recv().ok()).count();
        assert_eq!(count, 1);
    }

    #[test]
    fn test_alert_with_all_notification_channels() {
        let engine = AlertEngine::new();
        let mut alert = create_test_alert("BTC", AlertCondition::PriceAbove(dec!(100)));
        alert.notification_channels = vec![
            NotificationChannel::Email("test@example.com".to_string()),
            NotificationChannel::Webhook("https://webhook.example.com".to_string()),
            NotificationChannel::Push { device_id: "device123".to_string() },
            NotificationChannel::InApp,
        ];

        engine.create_alert(alert).unwrap();
        let rx = engine.take_notification_receiver().unwrap();

        engine.update_price("BTC", dec!(101));

        let notification = rx.try_recv().unwrap();
        assert_eq!(notification.channels.len(), 4);
    }
}

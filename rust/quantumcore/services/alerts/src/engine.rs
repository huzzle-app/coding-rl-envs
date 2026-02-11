use anyhow::Result;
use chrono::{DateTime, Utc};
use crossbeam::channel::{self, Receiver, Sender};
use dashmap::DashMap;
use parking_lot::RwLock;
use rust_decimal::Decimal;
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::Arc;
use uuid::Uuid;




#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Alert {
    pub id: Uuid,
    pub user_id: String,
    pub symbol: String,
    pub condition: AlertCondition,
    pub notification_channels: Vec<NotificationChannel>,
    pub created_at: DateTime<Utc>,
    pub triggered_at: Option<DateTime<Utc>>,
    pub active: bool,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum AlertCondition {
    PriceAbove(Decimal),
    PriceBelow(Decimal),
    PriceChange { threshold_percent: Decimal, window_seconds: u64 },
    VolumeSpike { threshold_multiplier: Decimal },
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum NotificationChannel {
    Email(String),
    Webhook(String),
    Push { device_id: String },
    InApp,
}

#[derive(Debug, Clone)]
pub struct AlertNotification {
    pub alert_id: Uuid,
    pub user_id: String,
    pub message: String,
    pub channels: Vec<NotificationChannel>,
    pub timestamp: DateTime<Utc>,
}

pub struct AlertEngine {
    alerts: DashMap<Uuid, Alert>,
    
    price_cache: DashMap<String, (Decimal, DateTime<Utc>)>,
    
    price_history: DashMap<String, Vec<(Decimal, DateTime<Utc>)>>,
    
    notification_tx: Sender<AlertNotification>,
    notification_rx: Arc<RwLock<Option<Receiver<AlertNotification>>>>,
    running: AtomicBool,
    
    recent_notifications: DashMap<Uuid, DateTime<Utc>>,
}

impl AlertEngine {
    pub fn new() -> Self {
        
        // If notifications aren't consumed fast enough, alerts are lost
        let (tx, rx) = channel::bounded(100);

        Self {
            alerts: DashMap::new(),
            price_cache: DashMap::new(),
            price_history: DashMap::new(),
            notification_tx: tx,
            notification_rx: Arc::new(RwLock::new(Some(rx))),
            running: AtomicBool::new(true),
            recent_notifications: DashMap::new(),
        }
    }

    pub fn create_alert(&self, alert: Alert) -> Result<Uuid> {
        let id = alert.id;
        self.alerts.insert(id, alert);
        Ok(id)
    }

    
    pub fn update_price(&self, symbol: &str, price: Decimal) {
        let now = Utc::now();

        // Update cache
        self.price_cache.insert(symbol.to_string(), (price, now));

        
        // This will grow unboundedly
        self.price_history
            .entry(symbol.to_string())
            .or_insert_with(Vec::new)
            .push((price, now));

        // Check alerts for this symbol
        self.check_alerts(symbol, price);
    }

    
    fn check_alerts(&self, symbol: &str, current_price: Decimal) {
        for mut alert_ref in self.alerts.iter_mut() {
            let alert = alert_ref.value_mut();

            if !alert.active || alert.symbol != symbol {
                continue;
            }

            let triggered = match &alert.condition {
                AlertCondition::PriceAbove(threshold) => current_price > *threshold,
                AlertCondition::PriceBelow(threshold) => current_price < *threshold,
                AlertCondition::PriceChange { threshold_percent, window_seconds } => {
                    
                    self.check_price_change(symbol, *threshold_percent, *window_seconds, current_price)
                }
                AlertCondition::VolumeSpike { .. } => {
                    
                    false
                }
            };

            if triggered {
                
                // Could spam notifications on price oscillation
                let notification = AlertNotification {
                    alert_id: alert.id,
                    user_id: alert.user_id.clone(),
                    message: format!("Alert triggered for {} at price {}", symbol, current_price),
                    channels: alert.notification_channels.clone(),
                    timestamp: Utc::now(),
                };

                
                match self.notification_tx.try_send(notification) {
                    Ok(_) => {
                        alert.triggered_at = Some(Utc::now());
                        alert.active = false;  // One-shot alert
                    }
                    Err(channel::TrySendError::Full(_)) => {
                        
                        tracing::error!("Notification channel full, dropping alert {}", alert.id);
                    }
                    Err(channel::TrySendError::Disconnected(_)) => {
                        tracing::error!("Notification channel disconnected");
                    }
                }
            }
        }
    }

    
    fn check_price_change(&self, symbol: &str, threshold: Decimal, window_secs: u64, current_price: Decimal) -> bool {
        let history = match self.price_history.get(symbol) {
            Some(h) => h,
            None => return false,
        };

        let now = Utc::now();
        let window_start = now - chrono::Duration::seconds(window_secs as i64);

        
        // Should be indexed by time for efficiency
        let old_price = history.iter()
            .filter(|(_, ts)| *ts >= window_start)
            .min_by_key(|(_, ts)| *ts)
            .map(|(p, _)| *p);

        match old_price {
            Some(old) if old != Decimal::ZERO => {
                let change_percent = ((current_price - old) / old) * Decimal::from(100);
                change_percent.abs() >= threshold
            }
            _ => false,
        }
    }

    
    pub fn take_notification_receiver(&self) -> Option<Receiver<AlertNotification>> {
        self.notification_rx.write().take()
    }

    
    pub fn prune_history(&self, max_age_seconds: u64) {
        let cutoff = Utc::now() - chrono::Duration::seconds(max_age_seconds as i64);

        
        // Could cause issues with concurrent price updates
        for mut entry in self.price_history.iter_mut() {
            entry.value_mut().retain(|(_, ts)| *ts >= cutoff);
        }

        
        // Map grows with symbols even if all history pruned
    }

    pub fn get_alert(&self, alert_id: Uuid) -> Option<Alert> {
        self.alerts.get(&alert_id).map(|a| a.clone())
    }

    pub fn get_user_alerts(&self, user_id: &str) -> Vec<Alert> {
        self.alerts.iter()
            .filter(|a| a.user_id == user_id)
            .map(|a| a.clone())
            .collect()
    }

    pub fn cancel_alert(&self, alert_id: Uuid) -> Result<()> {
        if let Some(mut alert) = self.alerts.get_mut(&alert_id) {
            alert.active = false;
            Ok(())
        } else {
            Err(anyhow::anyhow!("Alert not found"))
        }
    }

    pub fn stop(&self) {
        self.running.store(false, Ordering::SeqCst);
        
        // Pending alerts may be lost
    }
}

// Correct implementation for A4 (channel buffer):
// Use unbounded or auto-scaling buffer with backpressure:
//
// impl AlertEngine {
//     pub fn new() -> Self {
//         // Use tokio broadcast for multiple consumers
//         let (tx, _) = tokio::sync::broadcast::channel(10000);
//
//         // Or use unbounded with rate limiting
//         let (tx, rx) = tokio::sync::mpsc::unbounded_channel();
//
//         Self { ... }
//     }
//
//     async fn send_notification(&self, notification: AlertNotification) -> Result<()> {
//         // With backpressure and retry
//         let mut attempts = 0;
//         loop {
//             match self.notification_tx.try_send(notification.clone()) {
//                 Ok(_) => return Ok(()),
//                 Err(TrySendError::Full(_)) => {
//                     attempts += 1;
//                     if attempts > 3 {
//                         // Persist to disk for later delivery
//                         self.persist_notification(&notification).await?;
//                         return Ok(());
//                     }
//                     tokio::time::sleep(Duration::from_millis(100)).await;
//                 }
//                 Err(TrySendError::Disconnected(_)) => {
//                     return Err(anyhow::anyhow!("Channel disconnected"));
//                 }
//             }
//         }
//     }
// }

// Correct implementation for H1 (stale cache):
// Use TTL-based cache with proper invalidation:
//
// pub fn check_price_change(&self, symbol: &str, threshold: Decimal, window_secs: u64) -> bool {
//     // Use a proper time-series structure with O(log n) lookups
//     let now = Utc::now();
//     let window_start = now - Duration::seconds(window_secs);
//
//     // Binary search for the starting point
//     let history = self.price_history.get(symbol)?;
//     let start_idx = history.binary_search_by_key(&window_start, |(_, ts)| *ts)
//         .unwrap_or_else(|i| i);
//
//     // Get price at start of window
//     let old_price = history.get(start_idx).map(|(p, _)| *p)?;
//
//     // Calculate change
//     // ...
// }

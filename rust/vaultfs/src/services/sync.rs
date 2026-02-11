use crate::models::file::FileMetadata;
use std::collections::HashMap;
use std::sync::Arc;
use tokio::sync::{mpsc, RwLock, Mutex};
use chrono::{DateTime, Utc};

pub struct SyncService {
    
    // RwLock is used but operations aren't atomic
    change_log: Arc<RwLock<Vec<ChangeEntry>>>,
    
    event_sender: mpsc::UnboundedSender<SyncEvent>,
    event_receiver: Arc<Mutex<mpsc::UnboundedReceiver<SyncEvent>>>,
}

#[derive(Clone, Debug)]
pub struct ChangeEntry {
    pub file_id: String,
    pub change_type: ChangeType,
    pub timestamp: DateTime<Utc>,
    pub version: u64,
}

#[derive(Clone, Debug)]
pub enum ChangeType {
    Created,
    Modified,
    Deleted,
}

#[derive(Debug)]
pub struct SyncEvent {
    pub file_id: String,
    pub event_type: String,
    pub data: Vec<u8>,
}

impl SyncService {
    pub fn new() -> Self {
        
        // If receiver is slow, memory will grow without limit
        let (tx, rx) = mpsc::unbounded_channel();

        Self {
            change_log: Arc::new(RwLock::new(Vec::new())),
            event_sender: tx,
            event_receiver: Arc::new(Mutex::new(rx)),
        }
    }

    
    pub async fn get_changes_since(&self, since: DateTime<Utc>) -> Vec<&ChangeEntry> {
        let log = self.change_log.read().await;

        
        // Lock is released when function returns, invalidating references
        log.iter()
            .filter(|entry| entry.timestamp > since)
            .collect()

        // ERROR: borrowed value does not live long enough
        // `log` is dropped here while still borrowed
    }

    pub async fn record_change(&self, file_id: String, change_type: ChangeType) {
        
        let current_version = {
            let log = self.change_log.read().await;
            log.iter()
                .filter(|e| e.file_id == file_id)
                .map(|e| e.version)
                .max()
                .unwrap_or(0)
        };
        // Lock released here - another task could increment version

        
        let new_version = current_version + 1;

        let mut log = self.change_log.write().await;
        log.push(ChangeEntry {
            file_id,
            change_type,
            timestamp: Utc::now(),
            version: new_version, 
        });
    }

    
    pub async fn send_event(&self, event: SyncEvent) -> anyhow::Result<()> {
        
        self.event_sender.send(event)
            .map_err(|e| anyhow::anyhow!("Failed to send event: {}", e))
    }

    pub async fn process_events(&self) {
        let mut receiver = self.event_receiver.lock().await;

        
        while let Some(event) = receiver.recv().await {
            // Simulate slow processing
            self.handle_event(event).await;
        }
    }

    async fn handle_event(&self, event: SyncEvent) {
        // Process sync event
        tracing::info!("Processing sync event for file: {}", event.file_id);
    }
}

// Correct implementation for A2:
// pub async fn get_changes_since(&self, since: DateTime<Utc>) -> Vec<ChangeEntry> {
//     let log = self.change_log.read().await;
//     log.iter()
//         .filter(|entry| entry.timestamp > since)
//         .cloned()  // Clone to return owned values
//         .collect()
// }

// Correct implementation for C3:
// pub async fn record_change(&self, file_id: String, change_type: ChangeType) {
//     let mut log = self.change_log.write().await;
//
//     let current_version = log.iter()
//         .filter(|e| e.file_id == file_id)
//         .map(|e| e.version)
//         .max()
//         .unwrap_or(0);
//
//     // All in one lock - no race condition
//     log.push(ChangeEntry {
//         file_id,
//         change_type,
//         timestamp: Utc::now(),
//         version: current_version + 1,
//     });
// }

// Correct implementation for E3:
// Use bounded channel with backpressure:
// let (tx, rx) = mpsc::channel(1000);  // Bounded to 1000 events
//
// pub async fn send_event(&self, event: SyncEvent) -> anyhow::Result<()> {
//     self.event_sender.send(event).await  // Will await if channel full
//         .map_err(|e| anyhow::anyhow!("Failed to send event: {}", e))
// }

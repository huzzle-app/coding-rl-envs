use std::sync::Arc;
use tokio::sync::{mpsc, broadcast, Mutex};
use serde::{Serialize, Deserialize};

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct Notification {
    pub id: String,
    pub user_id: String,
    pub message: String,
    pub notification_type: NotificationType,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub enum NotificationType {
    FileShared,
    FileModified,
    SyncComplete,
    StorageWarning,
}

pub struct NotificationService {
    
    sender: broadcast::Sender<Notification>,
    pending: Arc<Mutex<Vec<Notification>>>,
}

impl NotificationService {
    pub fn new() -> Self {
        
        let (tx, _rx) = broadcast::channel(100);

        Self {
            sender: tx,
            pending: Arc::new(Mutex::new(Vec::new())),
        }
    }

    
    pub async fn send_notification(&self, notification: Notification) -> anyhow::Result<()> {
        
        // The receiver was dropped in new(), so this always fails
        self.sender.send(notification.clone())
            .map_err(|e| anyhow::anyhow!("Failed to send notification: {}", e))?;

        Ok(())
    }

    
    pub fn subscribe(&self) -> broadcast::Receiver<Notification> {
        self.sender.subscribe()
    }

    // Alternative implementation with issues
    pub async fn send_via_mpsc(&self, notification: Notification) {
        let (tx, mut rx) = mpsc::channel(1);

        
        tokio::spawn(async move {
            
            while let Some(notif) = rx.recv().await {
                println!("Received: {:?}", notif);
            }
        });

        
        tx.send(notification).await
            .expect("Receiver dropped"); // Panics if receiver gone
    }

    pub async fn add_pending(&self, notification: Notification) {
        let mut pending = self.pending.lock().await;
        pending.push(notification);
    }

    pub async fn flush_pending(&self) -> anyhow::Result<()> {
        let mut pending = self.pending.lock().await;

        for notification in pending.drain(..) {
            
            let _ = self.sender.send(notification);
        }

        Ok(())
    }
}

// Correct implementation:
// pub struct NotificationService {
//     sender: broadcast::Sender<Notification>,
//     // Keep a receiver to prevent "no receivers" error
//     _receiver: broadcast::Receiver<Notification>,
//     pending: Arc<Mutex<Vec<Notification>>>,
// }
//
// impl NotificationService {
//     pub fn new() -> Self {
//         let (tx, rx) = broadcast::channel(100);
//
//         Self {
//             sender: tx,
//             _receiver: rx,  // Keep receiver alive
//             pending: Arc::new(Mutex::new(Vec::new())),
//         }
//     }
//
//     pub async fn send_notification(&self, notification: Notification) -> anyhow::Result<()> {
//         // With receiver kept alive, this won't fail due to no receivers
//         match self.sender.send(notification.clone()) {
//             Ok(_) => Ok(()),
//             Err(_) => {
//                 // Still handle the case where send fails for other reasons
//                 self.add_pending(notification).await;
//                 Ok(())
//             }
//         }
//     }
// }

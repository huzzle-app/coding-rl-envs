//! WebSocket handling
//!
//! BUG B4: Future not Send
//! BUG B10: Thread pool exhaustion
//! BUG D8: Buffer not released

use axum::extract::ws::{Message, WebSocket};
use std::collections::HashMap;
use std::sync::Arc;
use parking_lot::RwLock;
use tokio::sync::broadcast;
use uuid::Uuid;

/// WebSocket connection manager
pub struct WebSocketManager {
    connections: Arc<RwLock<HashMap<Uuid, ConnectionState>>>,
    broadcast_tx: broadcast::Sender<String>,
    
    message_buffers: Arc<RwLock<HashMap<Uuid, Vec<u8>>>>,
}

struct ConnectionState {
    connected_at: std::time::Instant,
    last_ping: std::time::Instant,
    subscriptions: Vec<String>,
}

impl WebSocketManager {
    pub fn new() -> Self {
        let (broadcast_tx, _) = broadcast::channel(1024);
        Self {
            connections: Arc::new(RwLock::new(HashMap::new())),
            broadcast_tx,
            message_buffers: Arc::new(RwLock::new(HashMap::new())),
        }
    }

    /// Handle new WebSocket connection
    /
    pub async fn handle_connection(&self, mut socket: WebSocket) {
        let conn_id = Uuid::new_v4();
        let now = std::time::Instant::now();

        // Register connection
        {
            let mut conns = self.connections.write();
            conns.insert(conn_id, ConnectionState {
                connected_at: now,
                last_ping: now,
                subscriptions: Vec::new(),
            });
        }

        
        {
            let mut buffers = self.message_buffers.write();
            buffers.insert(conn_id, Vec::with_capacity(65536));
        }

        let connections = self.connections.clone();
        let buffers = self.message_buffers.clone();

        
        loop {
            tokio::select! {
                Some(msg) = socket.recv() => {
                    match msg {
                        Ok(Message::Text(text)) => {
                            tracing::debug!("Received: {}", text);
                        }
                        Ok(Message::Binary(data)) => {
                            
                            let mut bufs = buffers.write();
                            if let Some(buf) = bufs.get_mut(&conn_id) {
                                buf.extend_from_slice(&data);
                                // Never cleared!
                            }
                        }
                        Ok(Message::Ping(_)) => {
                            let mut conns = connections.write();
                            if let Some(state) = conns.get_mut(&conn_id) {
                                state.last_ping = std::time::Instant::now();
                            }
                        }
                        Ok(Message::Close(_)) => break,
                        Ok(_) => {}
                        Err(_) => break,
                    }
                }
                else => break,
            }
        }

        // Cleanup - but BUG D8: buffer not removed!
        {
            let mut conns = self.connections.write();
            conns.remove(&conn_id);
        }
        
    }

    /// Broadcast message to all connections
    pub fn broadcast(&self, message: String) {
        let _ = self.broadcast_tx.send(message);
    }

    /// Get connection count
    pub fn connection_count(&self) -> usize {
        self.connections.read().len()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_buffer_leak() {
        
        let _manager = WebSocketManager::new();
        // After connection closes, buffer should be removed
        // but it isn't
    }

    #[test]
    fn test_thread_pool_exhaustion() {
        
    }
}

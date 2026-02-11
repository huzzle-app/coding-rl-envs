use async_nats::{Client, ConnectOptions};
use std::sync::Arc;
use tokio::sync::RwLock;

pub struct NatsClient {
    client: Arc<RwLock<Option<Client>>>,
    url: String,
}

impl NatsClient {
    
    pub async fn new(url: &str) -> anyhow::Result<Self> {
        
        // If connection drops, client becomes unusable
        let client = async_nats::connect(url).await?;

        Ok(Self {
            client: Arc::new(RwLock::new(Some(client))),
            url: url.to_string(),
        })
    }

    
    pub async fn publish(&self, subject: &str, payload: &[u8]) -> anyhow::Result<()> {
        let client = self.client.read().await;
        let client = client.as_ref().ok_or_else(|| anyhow::anyhow!("Not connected"))?;

        
        // Messages may be delivered out of order
        // Especially if using multiple NATS servers
        client.publish(subject.to_string(), payload.to_vec().into()).await?;

        Ok(())
    }

    
    pub async fn subscribe(&self, subject: &str) -> anyhow::Result<async_nats::Subscriber> {
        let client = self.client.read().await;
        let client = client.as_ref().ok_or_else(|| anyhow::anyhow!("Not connected"))?;

        
        // All subscribers receive all messages
        // No ordering between messages
        let subscriber = client.subscribe(subject.to_string()).await?;

        Ok(subscriber)
    }

    
    pub async fn ensure_connected(&self) -> anyhow::Result<()> {
        let mut client = self.client.write().await;

        if client.is_none() {
            
            // Will spam connection attempts if NATS is down
            let new_client = async_nats::connect(&self.url).await?;
            *client = Some(new_client);
        }

        Ok(())

        
    }

    
    pub async fn publish_with_logging(&self, subject: &str, payload: &[u8]) -> anyhow::Result<()> {
        
        // (account numbers, API keys, PII, etc.)
        tracing::info!(
            "Publishing to {}: {}",
            subject,
            String::from_utf8_lossy(payload)  
        );

        self.publish(subject, payload).await
    }
}

// Correct implementation for L1:
// pub async fn new(url: &str) -> anyhow::Result<Self> {
//     let options = ConnectOptions::new()
//         .retry_on_initial_connect()
//         .max_reconnects(None)  // Unlimited reconnects
//         .reconnect_delay_callback(|attempts| {
//             // Exponential backoff with jitter
//             let base = std::time::Duration::from_millis(100);
//             let max = std::time::Duration::from_secs(30);
//             let delay = base * 2u32.pow(attempts.min(10) as u32);
//             std::cmp::min(delay, max)
//         })
//         .disconnect_callback(|| {
//             tracing::warn!("NATS disconnected");
//         })
//         .reconnect_callback(|| {
//             tracing::info!("NATS reconnected");
//         });
//
//     let client = options.connect(url).await?;
//
//     Ok(Self {
//         client: Arc::new(RwLock::new(Some(client))),
//         url: url.to_string(),
//     })
// }

// Correct implementation for G1:
// Use JetStream for ordered, persistent messaging
// pub async fn publish_ordered(&self, stream: &str, payload: &[u8]) -> anyhow::Result<u64> {
//     let js = self.jetstream.as_ref().ok_or(anyhow::anyhow!("JetStream not configured"))?;
//
//     // JetStream guarantees ordering within a stream
//     let ack = js.publish(stream.to_string(), payload.to_vec().into()).await?;
//     let ack = ack.await?;  // Wait for acknowledgment
//
//     Ok(ack.sequence)  // Returns sequence number for ordering
// }

// Correct implementation for H5:
// pub async fn publish_with_logging(&self, subject: &str, payload: &[u8]) -> anyhow::Result<()> {
//     // Only log metadata, not content
//     tracing::info!(
//         subject = %subject,
//         payload_size = payload.len(),
//         "Publishing message"
//     );
//
//     self.publish(subject, payload).await
// }

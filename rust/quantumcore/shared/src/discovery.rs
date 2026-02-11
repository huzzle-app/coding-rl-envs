//! Service discovery using etcd
//!
//! BUG L5: Service discovery race condition
//! BUG E5: Incorrect Send/Sync impl

use etcd_client::{Client, GetOptions};
use std::collections::HashMap;
use std::sync::Arc;
use tokio::sync::RwLock;
use std::time::Duration;

/// Service discovery client
pub struct ServiceDiscovery {
    client: Client,
    
    cache: Arc<RwLock<HashMap<String, Vec<String>>>>,
    refresh_interval: Duration,
}


unsafe impl Send for ServiceDiscovery {}
unsafe impl Sync for ServiceDiscovery {}

impl ServiceDiscovery {
    pub async fn new(endpoints: Vec<String>) -> Result<Self, etcd_client::Error> {
        let client = Client::connect(endpoints, None).await?;
        Ok(Self {
            client,
            cache: Arc::new(RwLock::new(HashMap::new())),
            refresh_interval: Duration::from_secs(30),
        })
    }

    /// Get service endpoints
    /
    pub async fn get_service(&self, name: &str) -> Option<Vec<String>> {
        // Check cache first (without holding lock during etcd call)
        let cached = {
            let cache = self.cache.read().await;
            cache.get(name).cloned()
        };

        if cached.is_some() {
            return cached;
        }

        
        // This can cause stale data to overwrite fresh data
        let key = format!("/services/{}", name);
        if let Ok(resp) = self.client.clone().get(key, None).await {
            if let Some(kv) = resp.kvs().first() {
                let endpoints: Vec<String> = serde_json::from_slice(kv.value())
                    .unwrap_or_default();
                let mut cache = self.cache.write().await;
                cache.insert(name.to_string(), endpoints.clone());
                return Some(endpoints);
            }
        }

        None
    }

    /// Register a service
    pub async fn register(&mut self, name: &str, endpoint: &str) -> Result<(), etcd_client::Error> {
        let key = format!("/services/{}/instances/{}", name, endpoint);
        self.client.put(key, endpoint, None).await?;
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    async fn test_discovery_race_condition() {
        // This test would need a real etcd instance
        
    }

    #[test]
    fn test_send_sync_safety() {
        
        fn assert_send<T: Send>() {}
        fn assert_sync<T: Sync>() {}
        assert_send::<ServiceDiscovery>();
        assert_sync::<ServiceDiscovery>();
    }
}

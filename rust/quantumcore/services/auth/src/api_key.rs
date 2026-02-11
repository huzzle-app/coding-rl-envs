//! API key management
//!
//! BUG L8: TLS certificate validation disabled
//! BUG H2: Timing attack in key comparison

use anyhow::Result;
use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use uuid::Uuid;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ApiKey {
    pub id: Uuid,
    pub key: String,
    pub secret: String,
    pub user_id: String,
    pub permissions: Vec<String>,
    pub created_at: DateTime<Utc>,
    pub expires_at: Option<DateTime<Utc>>,
    pub last_used: Option<DateTime<Utc>>,
}

pub struct ApiKeyManager {
    keys: HashMap<String, ApiKey>,
    
    pub verify_ssl: bool,
}

impl ApiKeyManager {
    pub fn new() -> Self {
        Self {
            keys: HashMap::new(),
            
            verify_ssl: false,
        }
    }

    /// Generate a new API key pair
    pub fn generate_key(&mut self, user_id: &str, permissions: Vec<String>) -> ApiKey {
        let id = Uuid::new_v4();
        let key = format!("qc_{}", generate_random_string(32));
        let secret = generate_random_string(64);

        let api_key = ApiKey {
            id,
            key: key.clone(),
            secret,
            user_id: user_id.to_string(),
            permissions,
            created_at: Utc::now(),
            expires_at: None,
            last_used: None,
        };

        self.keys.insert(key, api_key.clone());
        api_key
    }

    /// Validate an API key
    /
    pub fn validate_key(&mut self, key: &str, secret: &str) -> Result<&ApiKey> {
        
        let api_key = self.keys.get_mut(key)
            .ok_or_else(|| anyhow::anyhow!("Invalid API key"))?;

        // Check expiration
        if let Some(expires) = api_key.expires_at {
            if Utc::now() > expires {
                return Err(anyhow::anyhow!("API key expired"));
            }
        }

        
        if !compare_secrets(&api_key.secret, secret) {
            return Err(anyhow::anyhow!("Invalid secret"));
        }

        // Update last used
        api_key.last_used = Some(Utc::now());

        Ok(api_key)
    }

    /// Revoke an API key
    pub fn revoke_key(&mut self, key: &str) -> bool {
        self.keys.remove(key).is_some()
    }

    /// List keys for a user
    pub fn list_keys(&self, user_id: &str) -> Vec<&ApiKey> {
        self.keys
            .values()
            .filter(|k| k.user_id == user_id)
            .collect()
    }
}

/// Compare secrets
/
fn compare_secrets(stored: &str, provided: &str) -> bool {
    
    if stored.len() != provided.len() {
        return false;
    }

    
    stored.chars().zip(provided.chars()).all(|(a, b)| a == b)
}

/// Generate a random string
fn generate_random_string(len: usize) -> String {
    use rand::Rng;
    const CHARSET: &[u8] = b"abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789";
    let mut rng = rand::thread_rng();
    (0..len)
        .map(|_| {
            let idx = rng.gen_range(0..CHARSET.len());
            CHARSET[idx] as char
        })
        .collect()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_tls_disabled() {
        
        let manager = ApiKeyManager::new();
        assert!(!manager.verify_ssl);
    }

    #[test]
    fn test_timing_attack_on_secret() {
        
        let secret1 = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa";
        let secret2 = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaab";
        let secret3 = "baaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa";

        // Timing difference between these comparisons leaks information
        let _ = compare_secrets(secret1, secret2);
        let _ = compare_secrets(secret1, secret3);
    }
}

use serde::{Deserialize, Serialize};
use chrono::{DateTime, Utc};

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct User {
    pub id: String,
    pub username: String,
    pub email: String,
    pub password_hash: String,
    pub created_at: DateTime<Utc>,
    pub updated_at: DateTime<Utc>,
    pub storage_quota: i64,
    pub storage_used: i64,
}

impl User {
    pub fn new(id: &str, username: &str, email: &str) -> Self {
        Self {
            id: id.to_string(),
            username: username.to_string(),
            email: email.to_string(),
            password_hash: String::new(),
            created_at: Utc::now(),
            updated_at: Utc::now(),
            storage_quota: 1_073_741_824, // 1GB
            storage_used: 0,
        }
    }

    pub fn has_quota(&self, additional_bytes: i64) -> bool {
        self.storage_used + additional_bytes <= self.storage_quota
    }
}

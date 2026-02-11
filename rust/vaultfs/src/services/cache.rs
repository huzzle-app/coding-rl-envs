use deadpool_redis::{Config as RedisConfig, Pool, Runtime};
use redis::AsyncCommands;
use std::sync::Arc;
use serde::{Serialize, de::DeserializeOwned};

pub struct CacheService {
    pool: Pool,
}

impl CacheService {
    pub async fn new(redis_url: &str) -> anyhow::Result<Self> {
        let cfg = RedisConfig::from_url(redis_url);
        let pool = cfg.create_pool(Some(Runtime::Tokio1))?;

        Ok(Self { pool })
    }

    
    pub async fn get_with_fallback<'a, T, F>(
        &self,
        key: &'a str,
        fallback: F,
    ) -> anyhow::Result<&'a T>  
    where
        T: Serialize + DeserializeOwned,
        F: FnOnce() -> T,
    {
        let mut conn = self.pool.get().await?;
        let cached: Option<String> = conn.get(key).await?;

        if let Some(json) = cached {
            
            let value: T = serde_json::from_str(&json)?;
            return Ok(&value);  // ERROR: returns reference to local variable
        }

        // Compute fallback
        let value = fallback();
        let json = serde_json::to_string(&value)?;
        let _: () = conn.set(key, json).await?;

        Ok(&value)  // ERROR: returns reference to local variable

        // Correct implementation - return owned value:
        // pub async fn get_with_fallback<T, F>(...) -> anyhow::Result<T>
    }

    
    pub fn get_config_value<'a>(&'a self, key: &str) -> Option<&'a str> {
        // Would fetch from some internal config
        
        let value = format!("config_{}", key);
        Some(value.as_str())  // ERROR: temporary value dropped while borrowed
    }

    pub async fn get<T: DeserializeOwned>(&self, key: &str) -> anyhow::Result<Option<T>> {
        let mut conn = self.pool.get().await?;
        let cached: Option<String> = conn.get(key).await?;

        match cached {
            Some(json) => Ok(Some(serde_json::from_str(&json)?)),
            None => Ok(None),
        }
    }

    pub async fn set<T: Serialize>(&self, key: &str, value: &T, ttl_secs: usize) -> anyhow::Result<()> {
        let mut conn = self.pool.get().await?;
        let json = serde_json::to_string(value)?;
        let _: () = conn.set_ex(key, json, ttl_secs as u64).await?;
        Ok(())
    }

    pub async fn delete(&self, key: &str) -> anyhow::Result<()> {
        let mut conn = self.pool.get().await?;
        let _: () = conn.del(key).await?;
        Ok(())
    }
}

// Correct implementation:
// Return owned values instead of references to local data
//
// pub async fn get_with_fallback<T, F>(
//     &self,
//     key: &str,
//     fallback: F,
// ) -> anyhow::Result<T>
// where
//     T: Serialize + DeserializeOwned,
//     F: FnOnce() -> T,
// {
//     let mut conn = self.pool.get().await?;
//     let cached: Option<String> = conn.get(key).await?;
//
//     if let Some(json) = cached {
//         let value: T = serde_json::from_str(&json)?;
//         return Ok(value);  // Return owned value
//     }
//
//     let value = fallback();
//     let json = serde_json::to_string(&value)?;
//     let _: () = conn.set(key, json).await?;
//
//     Ok(value)  // Return owned value
// }

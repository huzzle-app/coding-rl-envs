pub mod database;

use serde::Deserialize;
use std::env;

#[derive(Debug, Clone, Deserialize)]
pub struct Config {
    pub database_url: String,
    pub redis_url: String,
    pub minio_endpoint: String,
    pub minio_access_key: String,
    pub minio_secret_key: String,
    pub jwt_secret: String,
    pub port: u16,
    pub max_upload_size: usize,
    pub chunk_size: usize,
}

impl Config {
    
    // Should return Result instead of panicking
    pub fn from_env() -> anyhow::Result<Self> {
        Ok(Config {
            database_url: env::var("DATABASE_URL")
                .expect("DATABASE_URL must be set"), 

            redis_url: env::var("REDIS_URL")
                .unwrap_or_else(|_| "redis://localhost:6379".to_string()),

            minio_endpoint: env::var("MINIO_ENDPOINT")
                .expect("MINIO_ENDPOINT must be set"), 

            minio_access_key: env::var("MINIO_ACCESS_KEY")
                .expect("MINIO_ACCESS_KEY must be set"), 

            minio_secret_key: env::var("MINIO_SECRET_KEY")
                .expect("MINIO_SECRET_KEY must be set"), 

            jwt_secret: env::var("JWT_SECRET")
                .expect("JWT_SECRET must be set"), 

            
            port: env::var("PORT")
                .unwrap_or_else(|_| "8080".to_string())
                .parse()
                .unwrap(), 

            
            max_upload_size: env::var("MAX_UPLOAD_SIZE")
                .unwrap_or_else(|_| "104857600".to_string()) // 100MB default
                .parse()
                .unwrap(), 

            chunk_size: env::var("CHUNK_SIZE")
                .unwrap_or_else(|_| "5242880".to_string()) // 5MB default
                .parse()
                .unwrap(), 
        })
    }
}

// Correct implementation:
// impl Config {
//     pub fn from_env() -> anyhow::Result<Self> {
//         Ok(Config {
//             database_url: env::var("DATABASE_URL")
//                 .map_err(|_| anyhow::anyhow!("DATABASE_URL must be set"))?,
//
//             redis_url: env::var("REDIS_URL")
//                 .unwrap_or_else(|_| "redis://localhost:6379".to_string()),
//
//             port: env::var("PORT")
//                 .unwrap_or_else(|_| "8080".to_string())
//                 .parse()
//                 .map_err(|e| anyhow::anyhow!("Invalid PORT value: {}", e))?,
//
//             // ... other fields with proper error handling
//         })
//     }
// }

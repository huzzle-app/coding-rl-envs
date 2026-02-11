pub mod storage;
pub mod sync;
pub mod versioning;
pub mod cache;
pub mod lock_manager;
pub mod notification;

use crate::config::Config;
use sqlx::PgPool;
use std::sync::Arc;
use tokio::sync::RwLock;
use dashmap::DashMap;

pub struct AppState {
    pub db: PgPool,
    pub config: Config,
    pub cache: Arc<cache::CacheService>,
    pub storage: Arc<storage::StorageService>,
    pub sync: Arc<sync::SyncService>,
    pub lock_manager: Arc<lock_manager::LockManager>,
    pub notification: Arc<notification::NotificationService>,
}

impl AppState {
    pub async fn new(db: PgPool, config: Config) -> anyhow::Result<Self> {
        let cache = Arc::new(cache::CacheService::new(&config.redis_url).await?);
        let storage = Arc::new(storage::StorageService::new(&config).await?);
        let sync = Arc::new(sync::SyncService::new());
        let lock_manager = Arc::new(lock_manager::LockManager::new());
        let notification = Arc::new(notification::NotificationService::new());

        Ok(Self {
            db,
            config,
            cache,
            storage,
            sync,
            lock_manager,
            notification,
        })
    }
}

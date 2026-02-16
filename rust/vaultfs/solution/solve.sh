#!/bin/bash
# Reference solution for VaultFS - fixes all 29 bugs
# Usage: bash solution/solve.sh
set -e

cd "$(dirname "$0")/.."
echo "Applying fixes for all 29 bugs in VaultFS..."

# ===========================================================================
# L1: Nested Runtime + L4: Graceful Shutdown (src/main.rs)
# ===========================================================================
echo "[L1+L4] Fixing nested runtime and graceful shutdown in main.rs"
cat <<'MAINEOF' > src/main.rs
use axum::{
    routing::{get, post, put, delete},
    Router,
};
use std::net::SocketAddr;
use std::sync::Arc;
use tokio::sync::RwLock;
use tracing_subscriber::{layer::SubscriberExt, util::SubscriberInitExt};

mod config;
mod handlers;
mod middleware;
mod models;
mod repository;
mod services;
mod storage;
mod sync;

use crate::config::Config;
use crate::services::AppState;

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    tracing_subscriber::registry()
        .with(tracing_subscriber::EnvFilter::new(
            std::env::var("RUST_LOG").unwrap_or_else(|_| "info".into()),
        ))
        .with(tracing_subscriber::fmt::layer())
        .init();

    let config = Config::from_env()?;

    // FIX L1: Use await directly instead of nested runtime
    let db_pool = config::database::create_pool(&config.database_url).await?;

    let state = Arc::new(AppState::new(db_pool, config.clone()).await?);
    let app = create_router(state.clone());

    let addr = SocketAddr::from(([0, 0, 0, 0], config.port));
    tracing::info!("Starting server on {}", addr);

    let listener = tokio::net::TcpListener::bind(addr).await?;
    // FIX L4: Use graceful shutdown
    axum::serve(listener, app)
        .with_graceful_shutdown(shutdown_signal())
        .await?;

    Ok(())
}

fn create_router(state: Arc<AppState>) -> Router {
    Router::new()
        .route("/api/files", get(handlers::files::list_files))
        .route("/api/files", post(handlers::files::upload_file))
        .route("/api/files/:id", get(handlers::files::get_file))
        .route("/api/files/:id", put(handlers::files::update_file))
        .route("/api/files/:id", delete(handlers::files::delete_file))
        .route("/api/files/:id/download", get(handlers::files::download_file))
        .route("/api/shares", post(handlers::shares::create_share))
        .route("/api/shares/:token", get(handlers::shares::get_share))
        .route("/api/sync/changes", get(handlers::sync::get_changes))
        .route("/api/sync/upload", post(handlers::sync::sync_upload))
        .route("/api/auth/login", post(handlers::auth::login))
        .route("/api/auth/register", post(handlers::auth::register))
        .route("/health", get(handlers::health::health_check))
        .with_state(state)
        .layer(middleware::auth::auth_layer())
}

// FIX L4: Remove #[allow(dead_code)] - now actually used
async fn shutdown_signal() {
    use tokio::signal;

    let ctrl_c = async {
        signal::ctrl_c()
            .await
            .expect("Failed to install Ctrl+C handler");
    };

    #[cfg(unix)]
    let terminate = async {
        signal::unix::signal(signal::unix::SignalKind::terminate())
            .expect("Failed to install signal handler")
            .recv()
            .await;
    };

    #[cfg(not(unix))]
    let terminate = std::future::pending::<()>();

    tokio::select! {
        _ = ctrl_c => {},
        _ = terminate => {},
    }

    tracing::info!("Shutdown signal received, starting graceful shutdown");
}
MAINEOF

# ===========================================================================
# L2: Pool Configuration (src/config/database.rs)
# ===========================================================================
echo "[L2] Fixing database pool configuration"
cat <<'DBEOF' > src/config/database.rs
use sqlx::postgres::{PgPool, PgPoolOptions};
use std::time::Duration;

pub async fn create_pool(database_url: &str) -> anyhow::Result<PgPool> {
    // FIX L2: Add proper pool configuration
    let pool = PgPoolOptions::new()
        .max_connections(25)
        .min_connections(5)
        .acquire_timeout(Duration::from_secs(5))
        .idle_timeout(Duration::from_secs(600))
        .max_lifetime(Duration::from_secs(1800))
        .test_before_acquire(true)
        .connect(database_url)
        .await?;

    Ok(pool)
}

pub async fn init_db(pool: &PgPool) -> anyhow::Result<()> {
    sqlx::query("SELECT 1")
        .execute(pool)
        .await
        .map_err(|e| anyhow::anyhow!("Database connection failed: {}", e))?;
    Ok(())
}
DBEOF

# ===========================================================================
# L3: Env Parsing (src/config/mod.rs)
# ===========================================================================
echo "[L3] Fixing config env parsing to return errors instead of panicking"
cat <<'CFGEOF' > src/config/mod.rs
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
    // FIX L3: Return Result instead of panicking
    pub fn from_env() -> anyhow::Result<Self> {
        Ok(Config {
            database_url: env::var("DATABASE_URL")
                .map_err(|_| anyhow::anyhow!("DATABASE_URL must be set"))?,
            redis_url: env::var("REDIS_URL")
                .unwrap_or_else(|_| "redis://localhost:6379".to_string()),
            minio_endpoint: env::var("MINIO_ENDPOINT")
                .map_err(|_| anyhow::anyhow!("MINIO_ENDPOINT must be set"))?,
            minio_access_key: env::var("MINIO_ACCESS_KEY")
                .map_err(|_| anyhow::anyhow!("MINIO_ACCESS_KEY must be set"))?,
            minio_secret_key: env::var("MINIO_SECRET_KEY")
                .map_err(|_| anyhow::anyhow!("MINIO_SECRET_KEY must be set"))?,
            jwt_secret: env::var("JWT_SECRET")
                .map_err(|_| anyhow::anyhow!("JWT_SECRET must be set"))?,
            port: env::var("PORT")
                .unwrap_or_else(|_| "8080".to_string())
                .parse()
                .map_err(|e| anyhow::anyhow!("Invalid PORT value: {}", e))?,
            max_upload_size: env::var("MAX_UPLOAD_SIZE")
                .unwrap_or_else(|_| "104857600".to_string())
                .parse()
                .map_err(|e| anyhow::anyhow!("Invalid MAX_UPLOAD_SIZE value: {}", e))?,
            chunk_size: env::var("CHUNK_SIZE")
                .unwrap_or_else(|_| "5242880".to_string())
                .parse()
                .map_err(|e| anyhow::anyhow!("Invalid CHUNK_SIZE value: {}", e))?,
        })
    }
}
CFGEOF

# ===========================================================================
# A1: Use After Move + C2: Blocking Async + D1: Unwrap on None (src/services/storage.rs)
# ===========================================================================
echo "[A1+C2+D1] Fixing storage.rs: use-after-move, blocking async, unwrap on None"
cat <<'STOREOF' > src/services/storage.rs
use crate::config::Config;
use crate::models::file::{FileMetadata, FileChunk};
use aws_sdk_s3::Client as S3Client;
use bytes::Bytes;
use sha2::{Sha256, Digest};

pub struct StorageService {
    s3_client: S3Client,
    bucket: String,
    chunk_size: usize,
}

impl StorageService {
    pub async fn new(config: &Config) -> anyhow::Result<Self> {
        let s3_config = aws_config::from_env()
            .endpoint_url(&config.minio_endpoint)
            .load()
            .await;

        let s3_client = S3Client::new(&s3_config);

        Ok(Self {
            s3_client,
            bucket: "vaultfs".to_string(),
            chunk_size: config.chunk_size,
        })
    }

    pub async fn upload_file(&self, file_id: &str, data: Bytes) -> anyhow::Result<FileMetadata> {
        // FIX A1: Capture size before any moves
        let size = data.len();
        let hash = self.calculate_hash(data.clone());
        let chunks = self.split_into_chunks(data);

        let mut metadata = FileMetadata::new(file_id);
        metadata.size = size;
        metadata.hash = hash;

        for (i, chunk) in chunks.into_iter().enumerate() {
            let chunk_meta = self.process_chunk(file_id, i, chunk).await?;
            metadata.chunks.push(chunk_meta);
        }

        Ok(metadata)
    }

    pub async fn save_to_disk(&self, path: &str, data: &[u8]) -> anyhow::Result<()> {
        // FIX C2: Use async I/O instead of blocking
        tokio::fs::write(path, data).await?;
        Ok(())
    }

    pub async fn get_file(&self, file_id: &str) -> anyhow::Result<Bytes> {
        let chunks = self.get_chunks(file_id).await?;

        // FIX D1: Handle empty chunks without panicking
        let _first_chunk = chunks.first()
            .ok_or_else(|| anyhow::anyhow!("File has no chunks"))?;

        let mut result = Vec::new();
        for chunk in chunks {
            let data = self.download_chunk(&chunk.key).await?;
            result.extend(data);
        }

        Ok(Bytes::from(result))
    }

    fn split_into_chunks(&self, data: Bytes) -> Vec<Bytes> {
        data.chunks(self.chunk_size)
            .map(|c| Bytes::copy_from_slice(c))
            .collect()
    }

    fn calculate_hash(&self, data: Bytes) -> String {
        let mut hasher = Sha256::new();
        hasher.update(&data);
        hex::encode(hasher.finalize())
    }

    async fn process_chunk(&self, file_id: &str, index: usize, data: Bytes) -> anyhow::Result<FileChunk> {
        let key = format!("{}/{}", file_id, index);

        self.s3_client
            .put_object()
            .bucket(&self.bucket)
            .key(&key)
            .body(data.into())
            .send()
            .await?;

        Ok(FileChunk {
            index,
            key,
            size: 0,
            hash: String::new(),
        })
    }

    async fn get_chunks(&self, _file_id: &str) -> anyhow::Result<Vec<FileChunk>> {
        Ok(vec![])
    }

    async fn download_chunk(&self, key: &str) -> anyhow::Result<Bytes> {
        let response = self.s3_client
            .get_object()
            .bucket(&self.bucket)
            .key(key)
            .send()
            .await?;

        let data = response.body.collect().await?;
        Ok(data.into_bytes())
    }
}
STOREOF

# ===========================================================================
# A2: Borrowed Value + C3: Race Condition + E3: Unbounded Channel (src/services/sync.rs)
# ===========================================================================
echo "[A2+C3+E3] Fixing sync.rs: return owned values, atomic record, bounded channel"
cat <<'SYNCEOF' > src/services/sync.rs
use std::sync::Arc;
use tokio::sync::{mpsc, RwLock, Mutex};
use chrono::{DateTime, Utc};

pub struct SyncService {
    change_log: Arc<RwLock<Vec<ChangeEntry>>>,
    // FIX E3: Use bounded channel
    event_sender: mpsc::Sender<SyncEvent>,
    event_receiver: Arc<Mutex<mpsc::Receiver<SyncEvent>>>,
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
        // FIX E3: Bounded channel with backpressure
        let (tx, rx) = mpsc::channel(1000);

        Self {
            change_log: Arc::new(RwLock::new(Vec::new())),
            event_sender: tx,
            event_receiver: Arc::new(Mutex::new(rx)),
        }
    }

    // FIX A2: Return owned Vec<ChangeEntry> instead of Vec<&ChangeEntry>
    pub async fn get_changes_since(&self, since: DateTime<Utc>) -> Vec<ChangeEntry> {
        let log = self.change_log.read().await;
        log.iter()
            .filter(|entry| entry.timestamp > since)
            .cloned()
            .collect()
    }

    // FIX C3: Atomic read+write with single write lock
    pub async fn record_change(&self, file_id: String, change_type: ChangeType) {
        let mut log = self.change_log.write().await;

        let current_version = log.iter()
            .filter(|e| e.file_id == file_id)
            .map(|e| e.version)
            .max()
            .unwrap_or(0);

        log.push(ChangeEntry {
            file_id,
            change_type,
            timestamp: Utc::now(),
            version: current_version + 1,
        });
    }

    pub async fn send_event(&self, event: SyncEvent) -> anyhow::Result<()> {
        // FIX E3: Use bounded send (awaits if full)
        self.event_sender.send(event).await
            .map_err(|e| anyhow::anyhow!("Failed to send event: {}", e))
    }

    pub async fn process_events(&self) {
        let mut receiver = self.event_receiver.lock().await;
        while let Some(event) = receiver.recv().await {
            self.handle_event(event).await;
        }
    }

    async fn handle_event(&self, event: SyncEvent) {
        tracing::info!("Processing sync event for file: {}", event.file_id);
    }
}
SYNCEOF

# ===========================================================================
# A3: Double Mutable Borrow (src/services/versioning.rs)
# ===========================================================================
echo "[A3] Fixing versioning.rs: double mutable borrow"
cat <<'VEREOF' > src/services/versioning.rs
use crate::models::file::FileMetadata;
use std::collections::HashMap;
use std::sync::Arc;
use tokio::sync::RwLock;

pub struct VersioningService {
    versions: Arc<RwLock<HashMap<String, Vec<FileVersion>>>>,
}

#[derive(Clone, Debug)]
pub struct FileVersion {
    pub version_number: u64,
    pub file_id: String,
    pub hash: String,
    pub size: usize,
    pub created_at: chrono::DateTime<chrono::Utc>,
}

impl VersioningService {
    pub fn new() -> Self {
        Self {
            versions: Arc::new(RwLock::new(HashMap::new())),
        }
    }

    pub async fn create_version(&self, file_id: &str, metadata: &FileMetadata) {
        let mut versions = self.versions.write().await;

        let file_versions = versions
            .entry(file_id.to_string())
            .or_insert_with(Vec::new);

        // FIX A3: Calculate version inline instead of passing &mut to helper
        let next_version = file_versions
            .last()
            .map(|v| v.version_number + 1)
            .unwrap_or(1);

        file_versions.push(FileVersion {
            version_number: next_version,
            file_id: file_id.to_string(),
            hash: metadata.hash.clone(),
            size: metadata.size,
            created_at: chrono::Utc::now(),
        });
    }

    // FIX A3: Take immutable slice reference
    fn calculate_next_version(&self, versions: &[FileVersion]) -> u64 {
        versions
            .last()
            .map(|v| v.version_number + 1)
            .unwrap_or(1)
    }

    pub async fn prune_old_versions(&self, file_id: &str, keep_count: usize) {
        let mut versions = self.versions.write().await;

        if let Some(file_versions) = versions.get_mut(file_id) {
            let to_delete: Vec<u64> = if file_versions.len() <= keep_count {
                vec![]
            } else {
                file_versions.iter()
                    .take(file_versions.len() - keep_count)
                    .map(|v| v.version_number)
                    .collect()
            };

            for version_num in to_delete {
                file_versions.retain(|v| v.version_number != version_num);
            }
        }
    }

    pub async fn get_version(&self, file_id: &str, version: u64) -> Option<FileVersion> {
        let versions = self.versions.read().await;
        versions
            .get(file_id)?
            .iter()
            .find(|v| v.version_number == version)
            .cloned()
    }

    pub async fn list_versions(&self, file_id: &str) -> Vec<FileVersion> {
        let versions = self.versions.read().await;
        versions
            .get(file_id)
            .cloned()
            .unwrap_or_default()
    }
}
VEREOF

# ===========================================================================
# A4: Moved Value in Loop + D2: Missing Match Arm + F1: Path Traversal (src/handlers/files.rs)
# ===========================================================================
echo "[A4+D2+F1] Fixing files.rs: move-in-loop, missing match arm, path traversal"
cat <<'FILESEOF' > src/handlers/files.rs
use axum::{
    extract::{Path, State, Query},
    http::StatusCode,
    response::IntoResponse,
    Json,
};
use serde::{Deserialize, Serialize};
use std::sync::Arc;
use std::path::PathBuf;

use crate::services::AppState;
use crate::models::file::FileMetadata;
use super::AppError;

#[derive(Deserialize)]
pub struct ListFilesQuery {
    pub path: Option<String>,
    pub limit: Option<usize>,
}

#[derive(Serialize)]
pub struct FileResponse {
    pub id: String,
    pub name: String,
    pub size: usize,
    pub path: String,
}

pub async fn list_files(
    State(state): State<Arc<AppState>>,
    Query(query): Query<ListFilesQuery>,
) -> Result<Json<Vec<FileResponse>>, AppError> {
    let path = query.path.unwrap_or_else(|| "/".to_string());
    let files = get_files_from_db(&state.db, &path).await?;

    let mut responses = Vec::new();

    for file in files {
        // FIX A4: Check .tmp BEFORE moving fields into FileResponse
        if file.name.ends_with(".tmp") {
            continue;
        }

        let response = FileResponse {
            id: file.id,
            name: file.name,
            size: file.size,
            path: file.path,
        };

        responses.push(response);
    }

    Ok(Json(responses))
}

pub async fn get_file(
    State(state): State<Arc<AppState>>,
    Path(file_id): Path<String>,
) -> Result<Json<FileResponse>, AppError> {
    let result = fetch_file(&state.db, &file_id).await;

    // FIX D2: Handle all match arms including Err
    match result {
        Ok(Some(file)) => Ok(Json(FileResponse {
            id: file.id,
            name: file.name,
            size: file.size,
            path: file.path,
        })),
        Ok(None) => {
            Err(AppError(anyhow::anyhow!("File not found")))
        }
        Err(e) => {
            Err(AppError(anyhow::anyhow!("Database error: {}", e)))
        }
    }
}

pub async fn download_file(
    State(_state): State<Arc<AppState>>,
    Path(file_path): Path<String>,
) -> Result<impl IntoResponse, AppError> {
    let base_path = PathBuf::from("/data/files");

    // FIX F1: Sanitize path to prevent traversal
    let requested_path = PathBuf::from(&file_path);
    let clean_path: PathBuf = requested_path
        .components()
        .filter(|c| !matches!(c, std::path::Component::ParentDir))
        .collect();

    let full_path = base_path.join(&clean_path);

    // Verify resolved path is within base directory
    let canonical = full_path.canonicalize()
        .map_err(|_| AppError(anyhow::anyhow!("Invalid path")))?;

    if !canonical.starts_with(&base_path) {
        return Err(AppError(anyhow::anyhow!("Access denied: path traversal")));
    }

    let content = tokio::fs::read(&canonical).await
        .map_err(|e| AppError(anyhow::anyhow!("Failed to read file: {}", e)))?;

    Ok((StatusCode::OK, content))
}

pub async fn upload_file(
    State(_state): State<Arc<AppState>>,
    Json(_payload): Json<UploadRequest>,
) -> Result<Json<FileResponse>, AppError> {
    todo!()
}

pub async fn update_file(
    State(_state): State<Arc<AppState>>,
    Path(_file_id): Path<String>,
    Json(_payload): Json<UpdateFileRequest>,
) -> Result<Json<FileResponse>, AppError> {
    todo!()
}

pub async fn delete_file(
    State(_state): State<Arc<AppState>>,
    Path(_file_id): Path<String>,
) -> Result<StatusCode, AppError> {
    todo!()
}

#[derive(Deserialize)]
pub struct UploadRequest {
    pub name: String,
    pub path: String,
    pub content: String,
}

#[derive(Deserialize)]
pub struct UpdateFileRequest {
    pub name: Option<String>,
    pub path: Option<String>,
}

async fn get_files_from_db(_db: &sqlx::PgPool, _path: &str) -> anyhow::Result<Vec<FileMetadata>> {
    Ok(vec![])
}

async fn fetch_file(_db: &sqlx::PgPool, _id: &str) -> anyhow::Result<Option<FileMetadata>> {
    Ok(None)
}
FILESEOF

# ===========================================================================
# A5: Partial Move (src/models/file.rs)
# ===========================================================================
echo "[A5] Fixing file.rs: partial move"
cat <<'FILEEOF' > src/models/file.rs
use serde::{Deserialize, Serialize};
use chrono::{DateTime, Utc};

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct FileMetadata {
    pub id: String,
    pub name: String,
    pub path: String,
    pub size: usize,
    pub hash: String,
    pub mime_type: String,
    pub owner_id: String,
    pub created_at: DateTime<Utc>,
    pub updated_at: DateTime<Utc>,
    pub chunks: Vec<FileChunk>,
    pub metadata: FileExtendedMetadata,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct FileChunk {
    pub index: usize,
    pub key: String,
    pub size: usize,
    pub hash: String,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct FileExtendedMetadata {
    pub description: Option<String>,
    pub tags: Vec<String>,
    pub custom_fields: std::collections::HashMap<String, String>,
}

impl FileMetadata {
    pub fn new(id: &str) -> Self {
        Self {
            id: id.to_string(),
            name: String::new(),
            path: String::new(),
            size: 0,
            hash: String::new(),
            mime_type: "application/octet-stream".to_string(),
            owner_id: String::new(),
            created_at: Utc::now(),
            updated_at: Utc::now(),
            chunks: Vec::new(),
            metadata: FileExtendedMetadata {
                description: None,
                tags: Vec::new(),
                custom_fields: std::collections::HashMap::new(),
            },
        }
    }

    // FIX A5: Move all fields together, no partial move
    pub fn extract_info(self) -> FileInfo {
        FileInfo {
            name: self.name,
            path: self.path,
            size: self.size,
            owner: self.owner_id,
        }
    }

    // FIX A5: Clone name before moving it
    pub fn split_metadata(self) -> (BasicInfo, ExtendedInfo) {
        let name_for_extended = self.name.clone();

        let basic = BasicInfo {
            id: self.id,
            name: self.name,
            size: self.size,
        };

        let extended = ExtendedInfo {
            description: self.metadata.description,
            tags: self.metadata.tags,
            file_name: name_for_extended,
        };

        (basic, extended)
    }
}

pub struct FileInfo {
    pub name: String,
    pub path: String,
    pub size: usize,
    pub owner: String,
}

pub struct BasicInfo {
    pub id: String,
    pub name: String,
    pub size: usize,
}

pub struct ExtendedInfo {
    pub description: Option<String>,
    pub tags: Vec<String>,
    pub file_name: String,
}
FILEEOF

# ===========================================================================
# B1: Reference to Local (src/services/cache.rs)
# ===========================================================================
echo "[B1] Fixing cache.rs: return owned values instead of references to locals"
cat <<'CACHEEOF' > src/services/cache.rs
use deadpool_redis::{Config as RedisConfig, Pool, Runtime};
use redis::AsyncCommands;
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

    // FIX B1: Return owned T, not &'a T
    pub async fn get_with_fallback<T, F>(
        &self,
        key: &str,
        fallback: F,
    ) -> anyhow::Result<T>
    where
        T: Serialize + DeserializeOwned,
        F: FnOnce() -> T,
    {
        let mut conn = self.pool.get().await?;
        let cached: Option<String> = conn.get(key).await?;

        if let Some(json) = cached {
            let value: T = serde_json::from_str(&json)?;
            return Ok(value);
        }

        let value = fallback();
        let json = serde_json::to_string(&value)?;
        let _: () = conn.set(key, json).await?;

        Ok(value)
    }

    // FIX B1: Return owned String, not &'a str
    pub fn get_config_value(&self, key: &str) -> Option<String> {
        let value = format!("config_{}", key);
        Some(value)
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
CACHEEOF

# ===========================================================================
# B2: Lifetime Annotation (src/repository/file_repo.rs)
# ===========================================================================
echo "[B2] Fixing file_repo.rs: unnecessary lifetime annotation"
cat <<'REPOEOF' > src/repository/file_repo.rs
use sqlx::PgPool;
use crate::models::file::FileMetadata;

pub struct FileRepository {
    pool: PgPool,
}

impl FileRepository {
    pub fn new(pool: PgPool) -> Self {
        Self { pool }
    }

    pub async fn find_by_id(&self, _id: &str) -> anyhow::Result<Option<FileMetadata>> {
        Ok(None)
    }

    // FIX B2: Remove unnecessary 'a lifetime
    pub async fn find_by_owner(&self, _owner_id: &str) -> anyhow::Result<Vec<FileMetadata>> {
        Ok(Vec::new())
    }

    pub async fn insert(&self, _file: &FileMetadata) -> anyhow::Result<()> {
        Ok(())
    }

    pub async fn delete(&self, _id: &str) -> anyhow::Result<()> {
        Ok(())
    }
}
REPOEOF

# ===========================================================================
# B3: Self-Referential Struct (src/models/chunk.rs)
# ===========================================================================
echo "[B3] Fixing chunk.rs: remove self-referential pointer"
cat <<'CHUNKEOF' > src/models/chunk.rs
// FIX B3: Remove self-referential data_ptr/data_len fields
pub struct Chunk {
    pub data: Vec<u8>,
    pub hash: String,
    pub index: usize,
}

impl Chunk {
    pub fn new(data: Vec<u8>, index: usize) -> Self {
        let hash = format!("{:x}", md5_simple(&data));
        Self { data, hash, index }
    }

    // FIX B3: Borrow from owned data instead of raw pointer
    pub fn get_data_ref(&self) -> &[u8] {
        &self.data
    }
}

fn md5_simple(data: &[u8]) -> u64 {
    let mut hash: u64 = 0;
    for &byte in data {
        hash = hash.wrapping_mul(31).wrapping_add(byte as u64);
    }
    hash
}
CHUNKEOF

# ===========================================================================
# B4: Lifetime Across Await (src/handlers/shares.rs)
# ===========================================================================
echo "[B4] Fixing shares.rs: owned types across await points"
cat <<'SHAREEOF' > src/handlers/shares.rs
use axum::{
    extract::{Path, State},
    Json,
};
use serde::{Deserialize, Serialize};
use std::sync::Arc;
use chrono::{DateTime, Utc};

use crate::services::AppState;
use super::AppError;

#[derive(Deserialize)]
pub struct CreateShareRequest {
    pub file_id: String,
    pub expires_at: Option<DateTime<Utc>>,
    pub password: Option<String>,
    pub max_downloads: Option<u32>,
}

#[derive(Serialize)]
pub struct ShareResponse {
    pub token: String,
    pub url: String,
    pub expires_at: Option<DateTime<Utc>>,
}

// FIX B4: Remove lifetime parameter, use owned String
pub async fn create_share(
    State(state): State<Arc<AppState>>,
    Json(request): Json<CreateShareRequest>,
) -> Result<Json<ShareResponse>, AppError> {
    let file_id = request.file_id.clone();

    validate_file(&file_id).await?;

    let share = create_share_for_file(
        &state,
        &file_id,
        request.expires_at,
        request.password.as_deref(),
    ).await?;

    Ok(Json(ShareResponse {
        token: share.token,
        url: format!("/shares/{}", share.token),
        expires_at: share.expires_at,
    }))
}

async fn validate_file(_file_ref: &str) -> anyhow::Result<()> {
    tokio::time::sleep(std::time::Duration::from_millis(10)).await;
    Ok(())
}

async fn create_share_for_file(
    _state: &AppState,
    file_ref: &str,
    expires_at: Option<DateTime<Utc>>,
    password: Option<&str>,
) -> anyhow::Result<Share> {
    tokio::time::sleep(std::time::Duration::from_millis(10)).await;

    Ok(Share {
        token: uuid::Uuid::new_v4().to_string(),
        file_id: file_ref.to_string(),
        expires_at,
        password_hash: password.map(|p| hash_password(p)),
    })
}

pub async fn get_share(
    State(_state): State<Arc<AppState>>,
    Path(_token): Path<String>,
) -> Result<Json<ShareResponse>, AppError> {
    todo!()
}

struct Share {
    token: String,
    file_id: String,
    expires_at: Option<DateTime<Utc>>,
    password_hash: Option<String>,
}

fn hash_password(password: &str) -> String {
    format!("hashed_{}", password)
}
SHAREEOF

# ===========================================================================
# C1: Deadlock (src/services/lock_manager.rs)
# ===========================================================================
echo "[C1] Fixing lock_manager.rs: consistent lock ordering"
cat <<'LOCKEOF' > src/services/lock_manager.rs
use std::collections::HashMap;
use std::sync::Arc;
use tokio::sync::Mutex;

pub struct LockManager {
    file_locks: Arc<Mutex<HashMap<String, Arc<Mutex<()>>>>>,
    user_locks: Arc<Mutex<HashMap<String, Arc<Mutex<()>>>>>,
}

impl LockManager {
    pub fn new() -> Self {
        Self {
            file_locks: Arc::new(Mutex::new(HashMap::new())),
            user_locks: Arc::new(Mutex::new(HashMap::new())),
        }
    }

    // FIX C1: Consistent lock ordering - always file then user
    pub async fn lock_file_for_user(&self, file_id: &str, user_id: &str) -> LockGuard {
        let file_lock = {
            let mut locks = self.file_locks.lock().await;
            locks.entry(file_id.to_string())
                .or_insert_with(|| Arc::new(Mutex::new(())))
                .clone()
        };

        let user_lock = {
            let mut locks = self.user_locks.lock().await;
            locks.entry(user_id.to_string())
                .or_insert_with(|| Arc::new(Mutex::new(())))
                .clone()
        };

        let _file_guard = file_lock.lock().await;
        let _user_guard = user_lock.lock().await;

        LockGuard {
            file_id: file_id.to_string(),
            user_id: user_id.to_string(),
        }
    }

    // FIX C1: Same order as lock_file_for_user (file first, then user)
    pub async fn lock_user_files(&self, user_id: &str, file_ids: &[String]) -> Vec<LockGuard> {
        let mut guards = Vec::new();

        // Sort file_ids for deterministic ordering
        let mut sorted_files = file_ids.to_vec();
        sorted_files.sort();

        for file_id in &sorted_files {
            let file_lock = {
                let mut locks = self.file_locks.lock().await;
                locks.entry(file_id.to_string())
                    .or_insert_with(|| Arc::new(Mutex::new(())))
                    .clone()
            };

            let _file_guard = file_lock.lock().await;

            guards.push(LockGuard {
                file_id: file_id.to_string(),
                user_id: user_id.to_string(),
            });
        }

        // Acquire user lock after all file locks (consistent with lock_file_for_user)
        let user_lock = {
            let mut locks = self.user_locks.lock().await;
            locks.entry(user_id.to_string())
                .or_insert_with(|| Arc::new(Mutex::new(())))
                .clone()
        };
        let _user_guard = user_lock.lock().await;

        guards
    }

    pub async fn acquire_file_lock(&self, _user_id: &str, file_id: &str) -> anyhow::Result<()> {
        let lock = {
            let mut locks = self.file_locks.lock().await;
            locks.entry(file_id.to_string())
                .or_insert_with(|| Arc::new(Mutex::new(())))
                .clone()
        };
        let _guard = lock.lock().await;
        Ok(())
    }

    pub async fn release_file_lock(&self, _user_id: &str, file_id: &str) -> anyhow::Result<()> {
        let mut locks = self.file_locks.lock().await;
        locks.remove(file_id);
        Ok(())
    }

    pub async fn acquire_user_lock(&self, user_id: &str) -> anyhow::Result<()> {
        let lock = {
            let mut locks = self.user_locks.lock().await;
            locks.entry(user_id.to_string())
                .or_insert_with(|| Arc::new(Mutex::new(())))
                .clone()
        };
        let _guard = lock.lock().await;
        Ok(())
    }

    pub async fn release_user_lock(&self, user_id: &str) -> anyhow::Result<()> {
        let mut locks = self.user_locks.lock().await;
        locks.remove(user_id);
        Ok(())
    }

    pub async fn release_lock(&self, file_id: &str) {
        let mut locks = self.file_locks.lock().await;
        locks.remove(file_id);
    }
}

pub struct LockGuard {
    pub file_id: String,
    pub user_id: String,
}
LOCKEOF

# ===========================================================================
# C4: Not Send (src/handlers/upload.rs)
# ===========================================================================
echo "[C4] Fixing upload.rs: use Arc<Mutex> instead of Rc<RefCell>"
cat <<'UPLOADEOF' > src/handlers/upload.rs
use axum::{
    extract::{Multipart, State},
    Json,
};
use std::sync::Arc;
use tokio::sync::Mutex;

use crate::services::AppState;
use super::AppError;

// FIX C4: Use Arc<Mutex> instead of Rc<RefCell> for Send+Sync
pub async fn upload_multipart(
    State(_state): State<Arc<AppState>>,
    mut multipart: Multipart,
) -> Result<Json<UploadResponse>, AppError> {
    let upload_progress = Arc::new(Mutex::new(UploadProgress::new()));
    let mut temp_storage = Vec::new();

    while let Some(field) = multipart.next_field().await? {
        let name = field.name().unwrap_or("unknown").to_string();
        let data = field.bytes().await?;

        upload_progress.lock().await.bytes_received += data.len();
        temp_storage.push((name, data));
    }

    let total_bytes = upload_progress.lock().await.bytes_received;

    Ok(Json(UploadResponse {
        files_uploaded: temp_storage.len(),
        total_bytes,
    }))
}

#[derive(serde::Serialize)]
pub struct UploadResponse {
    pub files_uploaded: usize,
    pub total_bytes: usize,
}

struct UploadProgress {
    bytes_received: usize,
    files_processed: usize,
}

impl UploadProgress {
    fn new() -> Self {
        Self {
            bytes_received: 0,
            files_processed: 0,
        }
    }
}

pub async fn upload_with_background_processing(
    State(_state): State<Arc<AppState>>,
    mut multipart: Multipart,
) -> Result<Json<UploadResponse>, AppError> {
    // FIX C4: Arc is Send+Sync
    let progress = Arc::new(Mutex::new(0usize));
    let progress_clone = progress.clone();

    tokio::spawn(async move {
        loop {
            let current = *progress_clone.lock().await;
            tracing::info!("Progress: {} bytes", current);
            tokio::time::sleep(std::time::Duration::from_secs(1)).await;
        }
    });

    while let Some(field) = multipart.next_field().await? {
        let data = field.bytes().await?;
        *progress.lock().await += data.len();
    }

    let total = *progress.lock().await;
    Ok(Json(UploadResponse {
        files_uploaded: 1,
        total_bytes: total,
    }))
}
UPLOADEOF

# ===========================================================================
# C5: Dropped Receiver (src/services/notification.rs)
# ===========================================================================
echo "[C5] Fixing notification.rs: keep receiver alive"
cat <<'NOTIFEOF' > src/services/notification.rs
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
    // FIX C5: Keep receiver alive so send() doesn't fail
    _receiver: broadcast::Receiver<Notification>,
    pending: Arc<Mutex<Vec<Notification>>>,
}

impl NotificationService {
    pub fn new() -> Self {
        let (tx, rx) = broadcast::channel(100);

        Self {
            sender: tx,
            _receiver: rx,
            pending: Arc::new(Mutex::new(Vec::new())),
        }
    }

    pub async fn send_notification(&self, notification: Notification) -> anyhow::Result<()> {
        match self.sender.send(notification.clone()) {
            Ok(_) => Ok(()),
            Err(_) => {
                self.add_pending(notification).await;
                Ok(())
            }
        }
    }

    pub fn subscribe(&self) -> broadcast::Receiver<Notification> {
        self.sender.subscribe()
    }

    pub async fn send_via_mpsc(&self, notification: Notification) {
        let (tx, mut rx) = mpsc::channel(1);

        tokio::spawn(async move {
            while let Some(notif) = rx.recv().await {
                println!("Received: {:?}", notif);
            }
        });

        tx.send(notification).await
            .expect("Receiver dropped");
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
NOTIFEOF

# ===========================================================================
# D3: Error Conversion (src/repository/user_repo.rs)
# ===========================================================================
echo "[D3] Fixing user_repo.rs: proper error conversion"
cat <<'UREPOEOF' > src/repository/user_repo.rs
use sqlx::PgPool;
use crate::models::user::User;

pub struct UserRepository {
    pool: PgPool,
}

impl UserRepository {
    pub fn new(pool: PgPool) -> Self {
        Self { pool }
    }

    pub async fn find_by_id(&self, _id: &str) -> anyhow::Result<Option<User>> {
        Ok(None)
    }

    pub async fn find_by_username(&self, _username: &str) -> anyhow::Result<Option<User>> {
        Ok(None)
    }

    // FIX D3: Use ? operator with proper error conversion, not .unwrap()
    pub async fn create(&self, _user: &User) -> anyhow::Result<()> {
        Ok(())
    }

    pub async fn update_quota(&self, _user_id: &str, _used: i64) -> anyhow::Result<()> {
        Ok(())
    }
}
UREPOEOF

# ===========================================================================
# D4: Panic in Drop (src/models/temp_file.rs)
# ===========================================================================
echo "[D4] Fixing temp_file.rs: no panic in drop"
cat <<'TMPEOF' > src/models/temp_file.rs
use std::path::PathBuf;
use std::fs;
use std::io;

/// Temporary file that should be cleaned up on drop
pub struct TempFile {
    path: PathBuf,
    should_cleanup: bool,
}

impl TempFile {
    pub fn new(path: PathBuf) -> io::Result<Self> {
        fs::File::create(&path)?;
        Ok(Self {
            path,
            should_cleanup: true,
        })
    }

    pub fn path(&self) -> &PathBuf {
        &self.path
    }

    pub fn persist(mut self) -> PathBuf {
        self.should_cleanup = false;
        self.path.clone()
    }

    pub fn write(&self, data: &[u8]) -> io::Result<()> {
        fs::write(&self.path, data)
    }

    pub fn read(&self) -> io::Result<Vec<u8>> {
        fs::read(&self.path)
    }
}

// FIX D4: Never panic in drop
impl Drop for TempFile {
    fn drop(&mut self) {
        if self.should_cleanup {
            if let Err(e) = fs::remove_file(&self.path) {
                eprintln!("Warning: Failed to remove temp file {:?}: {}", self.path, e);
            }
        }
    }
}

pub struct TempDirectory {
    path: PathBuf,
    files: Vec<TempFile>,
}

impl TempDirectory {
    pub fn new(path: PathBuf) -> io::Result<Self> {
        fs::create_dir_all(&path)?;
        Ok(Self {
            path,
            files: Vec::new(),
        })
    }

    pub fn add_file(&mut self, name: &str, content: &[u8]) -> io::Result<()> {
        let file_path = self.path.join(name);
        let file = TempFile::new(file_path)?;
        file.write(content)?;
        self.files.push(file);
        Ok(())
    }
}

// FIX D4: Never panic in drop
impl Drop for TempDirectory {
    fn drop(&mut self) {
        if let Err(e) = fs::remove_dir_all(&self.path) {
            eprintln!("Warning: Failed to remove temp directory {:?}: {}", self.path, e);
        }
    }
}
TMPEOF

# ===========================================================================
# E1: Rc Cycle (src/models/folder.rs)
# ===========================================================================
echo "[E1] Fixing folder.rs: use Weak for parent to break reference cycle"
cat <<'FOLDEOF' > src/models/folder.rs
use std::rc::{Rc, Weak};
use std::cell::RefCell;

// FIX E1: Use Weak for parent reference to break cycle
#[derive(Debug)]
pub struct Folder {
    pub id: String,
    pub name: String,
    pub parent: Option<Weak<RefCell<Folder>>>,
    pub children: Vec<Rc<RefCell<Folder>>>,
    pub files: Vec<String>,
}

impl Folder {
    pub fn new(id: &str, name: &str) -> Rc<RefCell<Self>> {
        Rc::new(RefCell::new(Self {
            id: id.to_string(),
            name: name.to_string(),
            parent: None,
            children: Vec::new(),
            files: Vec::new(),
        }))
    }

    // FIX E1: Use Weak reference for parent
    pub fn add_child(parent: &Rc<RefCell<Self>>, child: &Rc<RefCell<Self>>) {
        child.borrow_mut().parent = Some(Rc::downgrade(parent));
        parent.borrow_mut().children.push(Rc::clone(child));
    }

    pub fn get_path(&self) -> String {
        let mut parts = vec![self.name.clone()];
        let mut current = self.parent.as_ref().and_then(|w| w.upgrade());

        while let Some(parent) = current {
            parts.push(parent.borrow().name.clone());
            current = parent.borrow().parent.as_ref().and_then(|w| w.upgrade());
        }

        parts.reverse();
        parts.join("/")
    }

    pub fn remove_child(&mut self, child_id: &str) {
        self.children.retain(|c| c.borrow().id != child_id);
    }
}
FOLDEOF

# ===========================================================================
# F1: Path Traversal (src/utils.rs)
# ===========================================================================
echo "[F1] Fixing utils.rs: comprehensive path validation"
cat <<'UTILEOF' > src/utils.rs
/// Validate path: check literal .., URL-encoded, absolute paths, backslash
pub fn validate_path(path: &str) -> Result<String, String> {
    // FIX F1: Decode URL-encoded characters
    let decoded = urldecode(path);

    // Reject absolute paths
    if decoded.starts_with('/') || decoded.starts_with('\\') {
        return Err("Absolute paths not allowed".to_string());
    }

    // Reject file:// scheme
    if decoded.to_lowercase().starts_with("file://") {
        return Err("File scheme not allowed".to_string());
    }

    // Normalize backslashes and check for traversal
    let normalized = decoded.replace('\\', "/");
    if normalized.contains("..") {
        return Err(format!("Path traversal detected: {}", path));
    }

    Ok(path.to_string())
}

/// Validate webhook URL: reject internal/private addresses
pub fn validate_webhook_url(url: &str) -> Result<String, String> {
    if !url.starts_with("http://") && !url.starts_with("https://") {
        return Err("Invalid URL scheme".to_string());
    }

    // FIX F1: Check for internal addresses (SSRF prevention)
    let lower = url.to_lowercase();
    let blocked = [
        "localhost", "127.0.0.1", "0.0.0.0", "[::1]",
        "169.254.169.254", "10.", "172.16.", "192.168.",
    ];

    for pattern in &blocked {
        if lower.contains(pattern) {
            return Err(format!("Internal address not allowed: {}", url));
        }
    }

    Ok(url.to_string())
}

fn urldecode(s: &str) -> String {
    let mut result = String::new();
    let mut chars = s.chars();
    while let Some(c) = chars.next() {
        if c == '%' {
            let hex: String = chars.by_ref().take(2).collect();
            if hex.len() == 2 {
                if let Ok(byte) = u8::from_str_radix(&hex, 16) {
                    result.push(byte as char);
                    continue;
                }
            }
            result.push('%');
            result.push_str(&hex);
        } else {
            result.push(c);
        }
    }
    result
}
UTILEOF

# ===========================================================================
# F2: SQL Injection (src/repository/search.rs)
# ===========================================================================
echo "[F2] Fixing search.rs: parameterized queries"
cat <<'SRCHEOF' > src/repository/search.rs
use sqlx::PgPool;
use crate::models::file::FileMetadata;

pub struct SearchRepository {
    pool: PgPool,
}

impl SearchRepository {
    pub fn new(pool: PgPool) -> Self {
        Self { pool }
    }

    // FIX F2: Use parameterized queries
    pub async fn search_files(&self, query: &str, user_id: &str) -> anyhow::Result<Vec<FileMetadata>> {
        let pattern = format!("%{}%", query);
        let rows = sqlx::query_as::<_, FileRow>(
            "SELECT * FROM files WHERE name LIKE $1 AND owner_id = $2"
        )
        .bind(&pattern)
        .bind(user_id)
        .fetch_all(&self.pool)
        .await?;

        Ok(rows.into_iter().map(|r| r.into()).collect())
    }

    pub async fn search_by_tag(&self, tag: &str) -> anyhow::Result<Vec<FileMetadata>> {
        let rows = sqlx::query_as::<_, FileRow>(
            "SELECT * FROM files WHERE $1 = ANY(tags)"
        )
        .bind(tag)
        .fetch_all(&self.pool)
        .await?;

        Ok(rows.into_iter().map(|r| r.into()).collect())
    }

    // FIX F2: Validate sort column against whitelist
    pub async fn search_sorted(&self, query: &str, sort_by: &str) -> anyhow::Result<Vec<FileMetadata>> {
        let valid_columns = ["name", "created_at", "updated_at", "size"];
        let sort_column = if valid_columns.contains(&sort_by) {
            sort_by
        } else {
            "created_at"
        };

        let pattern = format!("%{}%", query);
        let sql = format!(
            "SELECT * FROM files WHERE name LIKE $1 ORDER BY {}",
            sort_column
        );

        let rows = sqlx::query_as::<_, FileRow>(&sql)
            .bind(&pattern)
            .fetch_all(&self.pool)
            .await?;

        Ok(rows.into_iter().map(|r| r.into()).collect())
    }
}

#[derive(sqlx::FromRow)]
struct FileRow {
    id: String,
    name: String,
    path: String,
    size: i64,
    hash: String,
    mime_type: String,
    owner_id: String,
    created_at: chrono::DateTime<chrono::Utc>,
    updated_at: chrono::DateTime<chrono::Utc>,
}

impl From<FileRow> for FileMetadata {
    fn from(row: FileRow) -> Self {
        FileMetadata {
            id: row.id,
            name: row.name,
            path: row.path,
            size: row.size as usize,
            hash: row.hash,
            mime_type: row.mime_type,
            owner_id: row.owner_id,
            created_at: row.created_at,
            updated_at: row.updated_at,
            chunks: Vec::new(),
            metadata: crate::models::file::FileExtendedMetadata {
                description: None,
                tags: Vec::new(),
                custom_fields: std::collections::HashMap::new(),
            },
        }
    }
}

// FIX F2: Parameterized query builder
pub fn build_search_query(_query: &str, _user_id: &str) -> String {
    // Return parameterized query template
    "SELECT * FROM files WHERE name LIKE $1 AND owner_id = $2".to_string()
}

pub fn build_sorted_query(_query: &str, sort_by: &str) -> String {
    let valid_columns = ["name", "created_at", "updated_at", "size"];
    let sort_column = if valid_columns.contains(&sort_by) {
        sort_by
    } else {
        "created_at"
    };
    format!(
        "SELECT * FROM files WHERE name LIKE $1 ORDER BY {}",
        sort_column
    )
}
SRCHEOF

# ===========================================================================
# F3: Timing Attack (src/middleware/auth.rs)
# ===========================================================================
echo "[F3] Fixing auth.rs: constant-time comparison"
cat <<'AUTHEOF' > src/middleware/auth.rs
use axum::{
    http::{Request, StatusCode},
    middleware::Next,
    response::Response,
    body::Body,
};
use jsonwebtoken::{decode, DecodingKey, Validation, Algorithm};
use serde::{Deserialize, Serialize};
use subtle::ConstantTimeEq;

#[derive(Debug, Serialize, Deserialize)]
pub struct Claims {
    pub sub: String,
    pub exp: usize,
    pub iat: usize,
}

pub fn auth_layer() -> tower::ServiceBuilder<tower::layer::util::Identity> {
    tower::ServiceBuilder::new()
}

pub async fn auth_middleware(
    request: Request<Body>,
    next: Next,
) -> Result<Response, StatusCode> {
    let auth_header = request
        .headers()
        .get("Authorization")
        .and_then(|h| h.to_str().ok());

    match auth_header {
        Some(header) if header.starts_with("Bearer ") => {
            let token = &header[7..];
            if validate_token(token) {
                Ok(next.run(request).await)
            } else {
                Err(StatusCode::UNAUTHORIZED)
            }
        }
        _ => Err(StatusCode::UNAUTHORIZED),
    }
}

fn validate_token(token: &str) -> bool {
    let secret = std::env::var("JWT_SECRET").unwrap_or_else(|_| "secret".to_string());
    let key = DecodingKey::from_secret(secret.as_bytes());
    decode::<Claims>(token, &key, &Validation::new(Algorithm::HS256)).is_ok()
}

// FIX F3: Use constant-time comparison
pub fn verify_api_key(provided: &str, expected: &str) -> bool {
    provided.as_bytes().ct_eq(expected.as_bytes()).into()
}

// FIX F3: Use constant-time comparison
pub fn verify_signature(provided: &[u8], expected: &[u8]) -> bool {
    if provided.len() != expected.len() {
        return false;
    }
    provided.ct_eq(expected).into()
}

// FIX F3: Use constant-time comparison
pub fn verify_hash(provided_hash: &str, stored_hash: &str) -> bool {
    provided_hash.as_bytes().ct_eq(stored_hash.as_bytes()).into()
}

pub fn validate_jwt(token: &str, secret: &str) -> Result<Claims, jsonwebtoken::errors::Error> {
    let key = DecodingKey::from_secret(secret.as_bytes());
    let data = decode::<Claims>(token, &key, &Validation::new(Algorithm::HS256))?;
    Ok(data.claims)
}
AUTHEOF

# ===========================================================================
# F4: Unsafe Mmap (src/storage/mmap.rs)
# ===========================================================================
echo "[F4] Fixing mmap.rs: keep file handle alive, bounds checking"
cat <<'MMAPEOF' > src/storage/mmap.rs
use std::fs::File;
use std::path::Path;

/// Memory-mapped file for efficient large file handling
pub struct MappedFile {
    ptr: *mut u8,
    len: usize,
    // FIX F4: Keep file handle alive for lifetime of mapping
    _file: File,
}

impl MappedFile {
    pub unsafe fn open(path: &Path) -> std::io::Result<Self> {
        let file = File::open(path)?;
        let metadata = file.metadata()?;
        let len = metadata.len() as usize;

        let ptr = libc::mmap(
            std::ptr::null_mut(),
            len,
            libc::PROT_READ,
            libc::MAP_PRIVATE,
            std::os::unix::io::AsRawFd::as_raw_fd(&file),
            0,
        ) as *mut u8;

        if ptr == libc::MAP_FAILED as *mut u8 {
            return Err(std::io::Error::last_os_error());
        }

        // FIX F4: Keep file handle alive
        Ok(Self { ptr, len, _file: file })
    }

    pub unsafe fn as_slice(&self) -> &[u8] {
        std::slice::from_raw_parts(self.ptr, self.len)
    }

    // FIX F4: Bounds checking before read
    pub unsafe fn read_at(&self, offset: usize, len: usize) -> Vec<u8> {
        if offset >= self.len || offset + len > self.len {
            return Vec::new();
        }
        let ptr = self.ptr.add(offset);
        std::slice::from_raw_parts(ptr, len).to_vec()
    }
}

impl Drop for MappedFile {
    fn drop(&mut self) {
        unsafe {
            libc::munmap(self.ptr as *mut libc::c_void, self.len);
        }
    }
}

unsafe impl Send for MappedFile {}
unsafe impl Sync for MappedFile {}
MMAPEOF

echo ""
echo "All 29 bugs fixed successfully!"
echo "Run 'cargo test' to verify."

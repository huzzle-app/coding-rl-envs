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


// This will panic because we're already in a runtime
#[tokio::main]
async fn main() -> anyhow::Result<()> {
    // Initialize tracing
    tracing_subscriber::registry()
        .with(tracing_subscriber::EnvFilter::new(
            std::env::var("RUST_LOG").unwrap_or_else(|_| "info".into()),
        ))
        .with(tracing_subscriber::fmt::layer())
        .init();

    // Load configuration
    let config = Config::from_env()?;

    
    // Some initialization code might do this incorrectly
    let db_pool = {
        
        let rt = tokio::runtime::Runtime::new().unwrap();
        rt.block_on(async {
            config::database::create_pool(&config.database_url).await
        })?
    };

    // Create application state
    let state = Arc::new(AppState::new(db_pool, config.clone()).await?);

    // Build router
    let app = create_router(state.clone());

    
    // Server will abruptly terminate on SIGTERM, potentially corrupting data
    let addr = SocketAddr::from(([0, 0, 0, 0], config.port));
    tracing::info!("Starting server on {}", addr);

    
    // Should use: axum::serve(...).with_graceful_shutdown(shutdown_signal())
    let listener = tokio::net::TcpListener::bind(addr).await?;
    axum::serve(listener, app).await?;

    Ok(())
}

fn create_router(state: Arc<AppState>) -> Router {
    Router::new()
        // File operations
        .route("/api/files", get(handlers::files::list_files))
        .route("/api/files", post(handlers::files::upload_file))
        .route("/api/files/:id", get(handlers::files::get_file))
        .route("/api/files/:id", put(handlers::files::update_file))
        .route("/api/files/:id", delete(handlers::files::delete_file))
        .route("/api/files/:id/download", get(handlers::files::download_file))
        // Shares
        .route("/api/shares", post(handlers::shares::create_share))
        .route("/api/shares/:token", get(handlers::shares::get_share))
        // Sync
        .route("/api/sync/changes", get(handlers::sync::get_changes))
        .route("/api/sync/upload", post(handlers::sync::sync_upload))
        // Auth
        .route("/api/auth/login", post(handlers::auth::login))
        .route("/api/auth/register", post(handlers::auth::register))
        // Health
        .route("/health", get(handlers::health::health_check))
        .with_state(state)
        .layer(middleware::auth::auth_layer())
}


// Graceful shutdown should wait for in-flight requests
#[allow(dead_code)]
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

// Correct implementation:
// #[tokio::main]
// async fn main() -> anyhow::Result<()> {
//     // ... initialization ...
//
//     // Don't create nested runtime - use await directly
//     let db_pool = config::database::create_pool(&config.database_url).await?;
//
//     // ... create router ...
//
//     // Use graceful shutdown
//     axum::serve(listener, app)
//         .with_graceful_shutdown(shutdown_signal())
//         .await?;
//
//     Ok(())
// }

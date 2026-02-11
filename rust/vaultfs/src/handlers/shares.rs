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


pub async fn create_share<'a>(
    State(state): State<Arc<AppState>>,
    Json(request): Json<CreateShareRequest>,
) -> Result<Json<ShareResponse>, AppError> {
    
    let file_ref = get_file_reference(&request.file_id);

    
    validate_file(file_ref).await?;

    
    let share = create_share_for_file(
        &state,
        file_ref,  // ERROR: borrowed value does not live long enough
        request.expires_at,
        request.password.as_deref(),
    ).await?;

    Ok(Json(ShareResponse {
        token: share.token,
        url: format!("/shares/{}", share.token),
        expires_at: share.expires_at,
    }))
}


fn get_file_reference<'a>(file_id: &'a str) -> &'a str {
    // In reality this might do some lookup
    file_id
}


async fn validate_file(file_ref: &str) -> anyhow::Result<()> {
    // Simulated async validation
    tokio::time::sleep(std::time::Duration::from_millis(10)).await;
    Ok(())
}


async fn create_share_for_file<'a>(
    state: &AppState,
    file_ref: &'a str,
    expires_at: Option<DateTime<Utc>>,
    password: Option<&str>,
) -> anyhow::Result<Share> {
    // Async operations with borrowed data
    tokio::time::sleep(std::time::Duration::from_millis(10)).await;

    Ok(Share {
        token: uuid::Uuid::new_v4().to_string(),
        file_id: file_ref.to_string(),
        expires_at,
        password_hash: password.map(|p| hash_password(p)),
    })
}

pub async fn get_share(
    State(state): State<Arc<AppState>>,
    Path(token): Path<String>,
) -> Result<Json<ShareResponse>, AppError> {
    // Implementation
    todo!()
}

struct Share {
    token: String,
    file_id: String,
    expires_at: Option<DateTime<Utc>>,
    password_hash: Option<String>,
}

fn hash_password(password: &str) -> String {
    // Would use proper hashing
    format!("hashed_{}", password)
}

// Correct implementation:
// Use owned types instead of references across async boundaries
//
// pub async fn create_share(
//     State(state): State<Arc<AppState>>,
//     Json(request): Json<CreateShareRequest>,
// ) -> Result<Json<ShareResponse>, AppError> {
//     // Clone to owned String instead of reference
//     let file_id = request.file_id.clone();
//
//     validate_file(&file_id).await?;
//
//     let share = create_share_for_file(
//         &state,
//         &file_id,  // Now borrowing from owned String
//         request.expires_at,
//         request.password.as_deref(),
//     ).await?;
//
//     Ok(Json(ShareResponse { ... }))
// }
//
// Or use 'static bounds:
// async fn create_share_for_file(
//     state: &AppState,
//     file_id: String,  // Take owned String
//     ...
// ) -> anyhow::Result<Share>

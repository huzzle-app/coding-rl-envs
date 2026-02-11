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

    // Simulate getting files from database
    let files = get_files_from_db(&state.db, &path).await?;

    let mut responses = Vec::new();

    
    for file in files {
        
        let response = FileResponse {
            id: file.id,
            name: file.name, // file.name moved
            size: file.size,
            path: file.path,
        };

        
        if file.name.ends_with(".tmp") {  // ERROR: use of moved value
            continue;
        }

        responses.push(response);
    }

    Ok(Json(responses))
}


pub async fn get_file(
    State(state): State<Arc<AppState>>,
    Path(file_id): Path<String>,
) -> Result<Json<FileResponse>, AppError> {
    let result = fetch_file(&state.db, &file_id).await;

    
    match result {
        Ok(Some(file)) => Ok(Json(FileResponse {
            id: file.id,
            name: file.name,
            size: file.size,
            path: file.path,
        })),
        Ok(None) => {
            // File not found case handled
            Err(AppError(anyhow::anyhow!("File not found")))
        }
        
        // If fetch_file returns Err, this won't compile
        // or if using _ => panic, it's still a bug
    }
}


pub async fn download_file(
    State(state): State<Arc<AppState>>,
    Path(file_path): Path<String>,
) -> Result<impl IntoResponse, AppError> {
    
    // Attacker could use: ../../../etc/passwd
    let base_path = PathBuf::from("/data/files");

    
    let full_path = base_path.join(&file_path);

    
    // full_path could be /data/files/../../../etc/passwd = /etc/passwd

    // Read file without checking if it's within allowed directory
    let content = tokio::fs::read(&full_path).await
        .map_err(|e| AppError(anyhow::anyhow!("Failed to read file: {}", e)))?;

    Ok((StatusCode::OK, content))
}

pub async fn upload_file(
    State(state): State<Arc<AppState>>,
    Json(payload): Json<UploadRequest>,
) -> Result<Json<FileResponse>, AppError> {
    // Implementation
    todo!()
}

pub async fn update_file(
    State(state): State<Arc<AppState>>,
    Path(file_id): Path<String>,
    Json(payload): Json<UpdateFileRequest>,
) -> Result<Json<FileResponse>, AppError> {
    todo!()
}

pub async fn delete_file(
    State(state): State<Arc<AppState>>,
    Path(file_id): Path<String>,
) -> Result<StatusCode, AppError> {
    todo!()
}

#[derive(Deserialize)]
pub struct UploadRequest {
    pub name: String,
    pub path: String,
    pub content: String, // base64 encoded
}

#[derive(Deserialize)]
pub struct UpdateFileRequest {
    pub name: Option<String>,
    pub path: Option<String>,
}

// Helper functions (stubs)
async fn get_files_from_db(db: &sqlx::PgPool, path: &str) -> anyhow::Result<Vec<FileMetadata>> {
    Ok(vec![])
}

async fn fetch_file(db: &sqlx::PgPool, id: &str) -> anyhow::Result<Option<FileMetadata>> {
    Ok(None)
}

// Correct implementation for A4:
// for file in files {
//     // Check before moving
//     if file.name.ends_with(".tmp") {
//         continue;
//     }
//
//     responses.push(FileResponse {
//         id: file.id,
//         name: file.name,
//         size: file.size,
//         path: file.path,
//     });
// }

// Correct implementation for F1:
// pub async fn download_file(...) {
//     let base_path = PathBuf::from("/data/files");
//
//     // Sanitize the path
//     let requested_path = PathBuf::from(&file_path);
//
//     // Remove any parent directory references
//     let clean_path: PathBuf = requested_path
//         .components()
//         .filter(|c| !matches!(c, std::path::Component::ParentDir))
//         .collect();
//
//     let full_path = base_path.join(&clean_path);
//
//     // Verify the resolved path is within base_path
//     let canonical = full_path.canonicalize()
//         .map_err(|_| AppError(anyhow::anyhow!("Invalid path")))?;
//
//     if !canonical.starts_with(&base_path) {
//         return Err(AppError(anyhow::anyhow!("Access denied")));
//     }
//
//     // Now safe to read
//     let content = tokio::fs::read(&canonical).await?;
//     Ok((StatusCode::OK, content))
// }

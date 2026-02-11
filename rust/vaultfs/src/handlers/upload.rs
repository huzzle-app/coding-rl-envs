use axum::{
    extract::{Multipart, State},
    Json,
};
use std::sync::Arc;
use std::cell::RefCell;
use std::rc::Rc;

use crate::services::AppState;
use super::AppError;


pub async fn upload_multipart(
    State(state): State<Arc<AppState>>,
    mut multipart: Multipart,
) -> Result<Json<UploadResponse>, AppError> {
    
    let upload_progress = Rc::new(RefCell::new(UploadProgress::new()));

    
    let temp_storage = RefCell::new(Vec::new());

    while let Some(field) = multipart.next_field().await? {
        let name = field.name().unwrap_or("unknown").to_string();
        let data = field.bytes().await?;

        
        upload_progress.borrow_mut().bytes_received += data.len();

        
        temp_storage.borrow_mut().push((name, data));
    }

    // Process uploaded files
    
    // because it's not Send

    let total_bytes = upload_progress.borrow().bytes_received;

    Ok(Json(UploadResponse {
        files_uploaded: temp_storage.borrow().len(),
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
    State(state): State<Arc<AppState>>,
    mut multipart: Multipart,
) -> Result<Json<UploadResponse>, AppError> {
    let progress = Rc::new(RefCell::new(0usize));
    let progress_clone = progress.clone();

    
    // ERROR: future cannot be sent between threads safely
    tokio::spawn(async move {
        // This won't compile because Rc is not Send
        loop {
            let current = *progress_clone.borrow();
            tracing::info!("Progress: {} bytes", current);
            tokio::time::sleep(std::time::Duration::from_secs(1)).await;
        }
    });

    while let Some(field) = multipart.next_field().await? {
        let data = field.bytes().await?;
        *progress.borrow_mut() += data.len();
    }

    Ok(Json(UploadResponse {
        files_uploaded: 1,
        total_bytes: *progress.borrow(),
    }))
}

// Correct implementation:
// Use Arc<Mutex> instead of Rc<RefCell> for Send + Sync
//
// pub async fn upload_multipart(
//     State(state): State<Arc<AppState>>,
//     mut multipart: Multipart,
// ) -> Result<Json<UploadResponse>, AppError> {
//     // Arc is Send + Sync, Mutex is Send + Sync
//     let upload_progress = Arc::new(tokio::sync::Mutex::new(UploadProgress::new()));
//
//     // Use Vec directly, or wrap in Arc<Mutex> if sharing needed
//     let mut temp_storage = Vec::new();
//
//     while let Some(field) = multipart.next_field().await? {
//         let name = field.name().unwrap_or("unknown").to_string();
//         let data = field.bytes().await?;
//
//         // Lock is Send-safe
//         upload_progress.lock().await.bytes_received += data.len();
//
//         temp_storage.push((name, data));
//     }
//
//     let total_bytes = upload_progress.lock().await.bytes_received;
//
//     Ok(Json(UploadResponse {
//         files_uploaded: temp_storage.len(),
//         total_bytes,
//     }))
// }

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

        // Get or create version list for this file
        let file_versions = versions
            .entry(file_id.to_string())
            .or_insert_with(Vec::new);

        
        let next_version = self.calculate_next_version(file_versions);

        
        // when we try to push
        file_versions.push(FileVersion {
            version_number: next_version,
            file_id: file_id.to_string(),
            hash: metadata.hash.clone(),
            size: metadata.size,
            created_at: chrono::Utc::now(),
        });
    }

    
    fn calculate_next_version(&self, versions: &mut Vec<FileVersion>) -> u64 {
        
        versions
            .last()
            .map(|v| v.version_number + 1)
            .unwrap_or(1)
    }

    
    pub async fn prune_old_versions(&self, file_id: &str, keep_count: usize) {
        let mut versions = self.versions.write().await;

        if let Some(file_versions) = versions.get_mut(file_id) {
            
            let to_delete = self.get_versions_to_delete(file_versions, keep_count);

            
            for version_num in to_delete {
                file_versions.retain(|v| v.version_number != version_num);
            }
        }
    }

    fn get_versions_to_delete(&self, versions: &Vec<FileVersion>, keep_count: usize) -> Vec<u64> {
        if versions.len() <= keep_count {
            return vec![];
        }

        versions.iter()
            .take(versions.len() - keep_count)
            .map(|v| v.version_number)
            .collect()
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

// Correct implementation:
// fn calculate_next_version(versions: &[FileVersion]) -> u64 {
//     // Take immutable reference instead
//     versions
//         .last()
//         .map(|v| v.version_number + 1)
//         .unwrap_or(1)
// }
//
// pub async fn create_version(&self, file_id: &str, metadata: &FileMetadata) {
//     let mut versions = self.versions.write().await;
//     let file_versions = versions
//         .entry(file_id.to_string())
//         .or_insert_with(Vec::new);
//
//     // Calculate version before mutating
//     let next_version = file_versions
//         .last()
//         .map(|v| v.version_number + 1)
//         .unwrap_or(1);
//
//     file_versions.push(FileVersion {
//         version_number: next_version,
//         // ...
//     });
// }

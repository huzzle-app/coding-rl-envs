use crate::config::Config;
use crate::models::file::{FileMetadata, FileChunk};
use aws_sdk_s3::Client as S3Client;
use bytes::Bytes;
use std::sync::Arc;
use tokio::sync::Mutex;
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
        let chunks = self.split_into_chunks(data.clone()); // Clone needed but missing in buggy version

        let mut metadata = FileMetadata::new(file_id);

        
        let hash = self.calculate_hash(data);

        for (i, chunk) in chunks.into_iter().enumerate() {
            
            // which were created from the moved data
            let chunk_meta = self.process_chunk(file_id, i, chunk).await?;
            metadata.chunks.push(chunk_meta);
        }

        
        metadata.size = data.len(); // ERROR: value borrowed after move
        metadata.hash = hash;

        Ok(metadata)
    }

    pub async fn save_to_disk(&self, path: &str, data: &[u8]) -> anyhow::Result<()> {
        
        // This will block the Tokio runtime thread
        std::fs::write(path, data)?;

        
        std::fs::set_permissions(path, std::fs::Permissions::from_mode(0o644))?;

        Ok(())

        // Correct implementation:
        // tokio::fs::write(path, data).await?;
        // tokio::fs::set_permissions(path, ...).await?;
    }

    pub async fn get_file(&self, file_id: &str) -> anyhow::Result<Bytes> {
        let chunks = self.get_chunks(file_id).await?;

        
        let first_chunk = chunks.first().unwrap(); // Panics if no chunks!

        let mut result = Vec::new();
        for chunk in chunks {
            
            let data = self.download_chunk(&chunk.key).await?;
            result.extend(data);
        }

        Ok(Bytes::from(result))

        // Correct implementation:
        // let first_chunk = chunks.first()
        //     .ok_or_else(|| anyhow::anyhow!("File has no chunks"))?;
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

    async fn get_chunks(&self, file_id: &str) -> anyhow::Result<Vec<FileChunk>> {
        // Would query database for chunk metadata
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

// Correct implementation for A1:
// pub async fn upload_file(&self, file_id: &str, data: Bytes) -> anyhow::Result<FileMetadata> {
//     let size = data.len();  // Capture size before any moves
//     let hash = self.calculate_hash(data.clone());  // Clone for hash
//     let chunks = self.split_into_chunks(data);  // data moves here
//
//     let mut metadata = FileMetadata::new(file_id);
//     metadata.size = size;
//     metadata.hash = hash;
//
//     for (i, chunk) in chunks.into_iter().enumerate() {
//         let chunk_meta = self.process_chunk(file_id, i, chunk).await?;
//         metadata.chunks.push(chunk_meta);
//     }
//
//     Ok(metadata)
// }

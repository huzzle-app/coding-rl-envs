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

    
    pub fn extract_info(self) -> FileInfo {
        
        let name = self.name;

        
        let path = self.path;

        
        FileInfo {
            name,
            path,
            size: self.size,
            owner: self.owner_id, // ERROR: use of partially moved value
        }
    }

    
    pub fn split_metadata(self) -> (BasicInfo, ExtendedInfo) {
        // Move out some fields
        let basic = BasicInfo {
            id: self.id,
            name: self.name,
            size: self.size,
        };

        
        let extended = ExtendedInfo {
            description: self.metadata.description,
            tags: self.metadata.tags,
            
            file_name: self.name.clone(), // ERROR: use of moved value
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

// Correct implementation for A5:
// impl FileMetadata {
//     pub fn extract_info(self) -> FileInfo {
//         FileInfo {
//             name: self.name,
//             path: self.path,
//             size: self.size,
//             owner: self.owner_id,
//             // All fields moved together, self is fully consumed
//         }
//     }
//
//     // Or clone if you need to keep using self
//     pub fn extract_info_ref(&self) -> FileInfo {
//         FileInfo {
//             name: self.name.clone(),
//             path: self.path.clone(),
//             size: self.size,
//             owner: self.owner_id.clone(),
//         }
//     }
//
//     pub fn split_metadata(self) -> (BasicInfo, ExtendedInfo) {
//         // Capture needed values before any moves
//         let name_for_extended = self.name.clone();
//
//         let basic = BasicInfo {
//             id: self.id,
//             name: self.name,
//             size: self.size,
//         };
//
//         let extended = ExtendedInfo {
//             description: self.metadata.description,
//             tags: self.metadata.tags,
//             file_name: name_for_extended,
//         };
//
//         (basic, extended)
//     }
// }

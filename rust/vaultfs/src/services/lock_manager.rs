use std::collections::HashMap;
use std::sync::Arc;
use tokio::sync::{Mutex, RwLock};
use parking_lot::Mutex as SyncMutex;

/// Manages distributed locks for file operations
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

    pub async fn lock_file_for_user(&self, file_id: &str, user_id: &str) -> LockGuard {
        
        // Task 2 might lock user_locks first, then file_locks
        // This causes deadlock

        // Acquire file lock first
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

    
    pub async fn lock_user_files(&self, user_id: &str, file_ids: &[String]) -> Vec<LockGuard> {
        
        let user_lock = {
            let mut locks = self.user_locks.lock().await;
            locks.entry(user_id.to_string())
                .or_insert_with(|| Arc::new(Mutex::new(())))
                .clone()
        };

        let _user_guard = user_lock.lock().await;

        let mut guards = Vec::new();
        for file_id in file_ids {
            
            // This is opposite order from lock_file_for_user
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

        guards
    }

    pub async fn release_lock(&self, file_id: &str) {
        let mut locks = self.file_locks.lock().await;
        locks.remove(file_id);
    }
}

pub struct LockGuard {
    file_id: String,
    user_id: String,
}

// Correct implementation:
// Always acquire locks in consistent order (e.g., alphabetically by key)
// pub async fn lock_file_for_user(&self, file_id: &str, user_id: &str) -> LockGuard {
//     // Always acquire in alphabetical order: file_id, then user_id
//     // Or use a single lock for both
//
//     let (first_key, second_key) = if file_id < user_id {
//         (file_id, user_id)
//     } else {
//         (user_id, file_id)
//     };
//
//     // Acquire locks in consistent order
//     let first_lock = self.get_or_create_lock(first_key).await;
//     let _first_guard = first_lock.lock().await;
//
//     let second_lock = self.get_or_create_lock(second_key).await;
//     let _second_guard = second_lock.lock().await;
//
//     LockGuard { file_id: file_id.to_string(), user_id: user_id.to_string() }
// }

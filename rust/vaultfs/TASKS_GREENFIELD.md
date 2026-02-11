# VaultFS - Greenfield Development Tasks

These tasks require implementing **new modules from scratch** for the VaultFS distributed file storage platform. Each task follows existing architectural patterns (services in `src/services/`, repositories in `src/repository/`, models in `src/models/`).

---

## Task 1: Encryption at Rest Service

### Overview

Implement a client-side encryption service that encrypts files before storage and decrypts them on retrieval. The service should support multiple encryption algorithms and per-user key management.

### Module Location

Create `src/services/encryption.rs` and update `src/services/mod.rs`.

### Trait Contract

```rust
use async_trait::async_trait;
use bytes::Bytes;
use thiserror::Error;

/// Errors that can occur during encryption operations
#[derive(Error, Debug)]
pub enum EncryptionError {
    #[error("Key not found for user: {0}")]
    KeyNotFound(String),

    #[error("Invalid key format: {0}")]
    InvalidKeyFormat(String),

    #[error("Encryption failed: {0}")]
    EncryptionFailed(String),

    #[error("Decryption failed: {0}")]
    DecryptionFailed(String),

    #[error("Algorithm not supported: {0}")]
    UnsupportedAlgorithm(String),

    #[error("Key derivation failed: {0}")]
    KeyDerivationFailed(String),

    #[error("Storage error: {0}")]
    StorageError(String),
}

/// Supported encryption algorithms
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum EncryptionAlgorithm {
    /// AES-256-GCM (recommended)
    Aes256Gcm,
    /// ChaCha20-Poly1305 (alternative for hardware without AES-NI)
    ChaCha20Poly1305,
}

/// Metadata stored alongside encrypted files
#[derive(Debug, Clone)]
pub struct EncryptionMetadata {
    /// Algorithm used for encryption
    pub algorithm: EncryptionAlgorithm,
    /// Initialization vector / nonce
    pub iv: Vec<u8>,
    /// Key version for rotation support
    pub key_version: u32,
    /// Optional authentication tag (for AEAD ciphers)
    pub auth_tag: Option<Vec<u8>>,
}

/// Result of an encryption operation
#[derive(Debug)]
pub struct EncryptedData {
    /// The encrypted bytes
    pub ciphertext: Bytes,
    /// Metadata needed for decryption
    pub metadata: EncryptionMetadata,
}

/// Encryption service trait for file-level encryption
#[async_trait]
pub trait EncryptionService: Send + Sync {
    /// Encrypts file data for a specific user.
    ///
    /// # Arguments
    /// * `user_id` - The owner of the encryption key
    /// * `file_id` - Unique identifier for the file (used in key derivation)
    /// * `plaintext` - The unencrypted file data
    /// * `algorithm` - The encryption algorithm to use
    ///
    /// # Returns
    /// Encrypted data with metadata, or an error
    async fn encrypt(
        &self,
        user_id: &str,
        file_id: &str,
        plaintext: Bytes,
        algorithm: EncryptionAlgorithm,
    ) -> Result<EncryptedData, EncryptionError>;

    /// Decrypts file data using stored metadata.
    ///
    /// # Arguments
    /// * `user_id` - The owner of the encryption key
    /// * `file_id` - Unique identifier for the file
    /// * `ciphertext` - The encrypted data
    /// * `metadata` - Encryption metadata from the encrypt operation
    ///
    /// # Returns
    /// The decrypted plaintext, or an error
    async fn decrypt(
        &self,
        user_id: &str,
        file_id: &str,
        ciphertext: Bytes,
        metadata: &EncryptionMetadata,
    ) -> Result<Bytes, EncryptionError>;

    /// Generates or retrieves the master key for a user.
    /// Keys are derived from user credentials and stored encrypted.
    ///
    /// # Arguments
    /// * `user_id` - The user to generate/retrieve key for
    /// * `passphrase` - User's passphrase for key derivation
    ///
    /// # Returns
    /// Success or an error if key generation fails
    async fn initialize_user_key(
        &self,
        user_id: &str,
        passphrase: &str,
    ) -> Result<(), EncryptionError>;

    /// Rotates the encryption key for a user.
    /// All files must be re-encrypted with the new key.
    ///
    /// # Arguments
    /// * `user_id` - The user whose key should be rotated
    /// * `old_passphrase` - Current passphrase
    /// * `new_passphrase` - New passphrase
    ///
    /// # Returns
    /// The new key version number
    async fn rotate_key(
        &self,
        user_id: &str,
        old_passphrase: &str,
        new_passphrase: &str,
    ) -> Result<u32, EncryptionError>;

    /// Checks if a user has an initialized encryption key.
    async fn has_key(&self, user_id: &str) -> bool;
}
```

### Required Structs and Types

```rust
/// Service implementation
pub struct VaultEncryptionService {
    /// Key storage (Redis or database-backed)
    key_store: Arc<RwLock<HashMap<String, UserKeyMaterial>>>,
    /// Configuration
    config: EncryptionConfig,
}

/// Per-user key material
pub struct UserKeyMaterial {
    /// Encrypted master key (never stored in plaintext)
    encrypted_master_key: Vec<u8>,
    /// Salt for key derivation
    salt: Vec<u8>,
    /// Current key version
    version: u32,
    /// Key creation timestamp
    created_at: chrono::DateTime<chrono::Utc>,
    /// Last rotation timestamp
    rotated_at: Option<chrono::DateTime<chrono::Utc>>,
}

/// Configuration for the encryption service
pub struct EncryptionConfig {
    /// Default algorithm for new encryptions
    pub default_algorithm: EncryptionAlgorithm,
    /// Argon2 memory cost for key derivation
    pub argon2_memory_cost: u32,
    /// Argon2 time cost for key derivation
    pub argon2_time_cost: u32,
    /// Argon2 parallelism for key derivation
    pub argon2_parallelism: u32,
}
```

### Architectural Patterns to Follow

1. **Service Pattern**: Follow `StorageService` structure with `new()` constructor
2. **Async/Await**: All public methods must be async
3. **Error Handling**: Use `thiserror` for custom error types, return `Result`
4. **Thread Safety**: Use `Arc<RwLock<T>>` for shared mutable state
5. **Configuration**: Accept config from `Config` struct

### Integration Points

- Add `encryption: Arc<EncryptionService>` to `AppState`
- Integrate with `StorageService.upload_file()` to encrypt before storage
- Integrate with `StorageService.get_file()` to decrypt after retrieval
- Store `EncryptionMetadata` in `FileMetadata.metadata.custom_fields`

### Acceptance Criteria

1. **Unit Tests** (create `tests/encryption_tests.rs`)
   - Test encryption/decryption round-trip for both algorithms
   - Test key initialization and rotation
   - Test error cases (wrong passphrase, missing key, corrupted data)
   - Test concurrent access to key material
   - Minimum 15 test cases

2. **Coverage Requirements**
   - All public trait methods tested
   - Error paths tested
   - Edge cases: empty file, large file (>100MB chunks), special characters in IDs

3. **Security Requirements**
   - Keys never stored in plaintext
   - Constant-time comparison for authentication tags
   - Proper IV/nonce generation (cryptographically random)
   - Memory cleared after use (zeroize crate)

### Test Command

```bash
cargo test encryption
```

---

## Task 2: File Quota Manager

### Overview

Implement a quota management service that tracks storage usage per user and enforces limits. The service should support soft limits (warnings), hard limits (rejections), and quota inheritance for shared folders.

### Module Location

Create `src/services/quota.rs` and `src/repository/quota_repo.rs`.

### Trait Contract

```rust
use async_trait::async_trait;
use thiserror::Error;

/// Errors from quota operations
#[derive(Error, Debug)]
pub enum QuotaError {
    #[error("Quota exceeded: used {used} of {limit} bytes")]
    QuotaExceeded { used: u64, limit: u64 },

    #[error("Soft limit reached: used {used} of {limit} bytes (warning threshold: {threshold}%)")]
    SoftLimitReached { used: u64, limit: u64, threshold: u8 },

    #[error("User not found: {0}")]
    UserNotFound(String),

    #[error("Invalid quota configuration: {0}")]
    InvalidConfiguration(String),

    #[error("Database error: {0}")]
    DatabaseError(String),
}

/// Quota check result
#[derive(Debug, Clone)]
pub enum QuotaCheckResult {
    /// Within limits, operation allowed
    Allowed { remaining: u64 },
    /// Soft limit reached, warn but allow
    Warning { remaining: u64, percent_used: u8 },
    /// Hard limit exceeded, reject operation
    Denied { over_by: u64 },
}

/// Usage statistics for a user
#[derive(Debug, Clone)]
pub struct UsageStats {
    /// User ID
    pub user_id: String,
    /// Total bytes used
    pub bytes_used: u64,
    /// Total file count
    pub file_count: u64,
    /// Quota limit in bytes
    pub quota_limit: u64,
    /// Percentage of quota used
    pub percent_used: f64,
    /// Bytes remaining
    pub bytes_remaining: u64,
    /// Breakdown by file type
    pub usage_by_type: std::collections::HashMap<String, u64>,
}

/// Quota tier configuration
#[derive(Debug, Clone)]
pub struct QuotaTier {
    /// Tier name (e.g., "free", "pro", "enterprise")
    pub name: String,
    /// Storage limit in bytes
    pub storage_limit: u64,
    /// Maximum file size in bytes
    pub max_file_size: u64,
    /// Maximum file count
    pub max_file_count: Option<u64>,
    /// Soft limit percentage (0-100)
    pub soft_limit_percent: u8,
}

/// Quota management service trait
#[async_trait]
pub trait QuotaService: Send + Sync {
    /// Checks if a user can upload a file of the given size.
    ///
    /// # Arguments
    /// * `user_id` - The user attempting the upload
    /// * `file_size` - Size of the file in bytes
    ///
    /// # Returns
    /// The quota check result indicating if upload is allowed
    async fn check_upload(
        &self,
        user_id: &str,
        file_size: u64,
    ) -> Result<QuotaCheckResult, QuotaError>;

    /// Records a file upload, updating usage statistics.
    ///
    /// # Arguments
    /// * `user_id` - The owner of the file
    /// * `file_id` - Unique file identifier
    /// * `file_size` - Size of the uploaded file
    /// * `mime_type` - MIME type for category tracking
    async fn record_upload(
        &self,
        user_id: &str,
        file_id: &str,
        file_size: u64,
        mime_type: &str,
    ) -> Result<(), QuotaError>;

    /// Records a file deletion, updating usage statistics.
    ///
    /// # Arguments
    /// * `user_id` - The owner of the file
    /// * `file_id` - Unique file identifier
    /// * `file_size` - Size of the deleted file
    async fn record_deletion(
        &self,
        user_id: &str,
        file_id: &str,
        file_size: u64,
    ) -> Result<(), QuotaError>;

    /// Gets current usage statistics for a user.
    async fn get_usage(&self, user_id: &str) -> Result<UsageStats, QuotaError>;

    /// Gets the quota tier for a user.
    async fn get_tier(&self, user_id: &str) -> Result<QuotaTier, QuotaError>;

    /// Sets the quota tier for a user.
    ///
    /// # Arguments
    /// * `user_id` - The user to update
    /// * `tier_name` - Name of the tier to assign
    async fn set_tier(&self, user_id: &str, tier_name: &str) -> Result<(), QuotaError>;

    /// Recalculates usage for a user by scanning all files.
    /// Use when usage tracking becomes inconsistent.
    async fn recalculate_usage(&self, user_id: &str) -> Result<UsageStats, QuotaError>;

    /// Lists all users approaching their quota limit.
    ///
    /// # Arguments
    /// * `threshold_percent` - Minimum usage percentage to include (e.g., 80)
    async fn list_users_near_limit(
        &self,
        threshold_percent: u8,
    ) -> Result<Vec<UsageStats>, QuotaError>;
}
```

### Required Structs and Types

```rust
/// Service implementation
pub struct VaultQuotaService {
    /// Database connection pool
    db: sqlx::PgPool,
    /// In-memory usage cache for fast checks
    usage_cache: Arc<DashMap<String, CachedUsage>>,
    /// Quota tier definitions
    tiers: Arc<RwLock<HashMap<String, QuotaTier>>>,
    /// Configuration
    config: QuotaConfig,
}

/// Cached usage entry
pub struct CachedUsage {
    pub bytes_used: u64,
    pub file_count: u64,
    pub cached_at: std::time::Instant,
}

/// Configuration
pub struct QuotaConfig {
    /// How long to cache usage data
    pub cache_ttl_seconds: u64,
    /// Default tier for new users
    pub default_tier: String,
}

/// Repository for quota data persistence
pub struct QuotaRepository {
    pool: sqlx::PgPool,
}
```

### Repository Trait

```rust
#[async_trait]
pub trait QuotaRepository: Send + Sync {
    /// Gets the stored usage for a user
    async fn get_usage(&self, user_id: &str) -> Result<Option<StoredUsage>, QuotaError>;

    /// Updates usage atomically
    async fn update_usage(
        &self,
        user_id: &str,
        delta_bytes: i64,
        delta_files: i64,
    ) -> Result<StoredUsage, QuotaError>;

    /// Gets the tier assignment for a user
    async fn get_user_tier(&self, user_id: &str) -> Result<Option<String>, QuotaError>;

    /// Sets the tier for a user
    async fn set_user_tier(&self, user_id: &str, tier: &str) -> Result<(), QuotaError>;
}
```

### Architectural Patterns to Follow

1. **Repository Pattern**: Database access through `QuotaRepository`
2. **Caching**: Use `DashMap` for concurrent cache access (like existing code)
3. **Atomic Updates**: Use database transactions for usage updates
4. **Service Layer**: Business logic in service, data access in repository

### Integration Points

- Hook into `handlers/upload.rs` to check quota before accepting uploads
- Hook into `handlers/files.rs` delete handler to update usage
- Add quota info to `FileMetadata` responses
- Add `/api/quota` endpoint for user to check their usage

### Acceptance Criteria

1. **Unit Tests** (create `tests/quota_tests.rs`)
   - Test upload check with various quota states
   - Test usage recording and deletion
   - Test tier upgrades/downgrades
   - Test soft limit warnings
   - Test cache expiration
   - Test concurrent usage updates (race conditions)
   - Minimum 20 test cases

2. **Integration Tests**
   - Test with actual database (using test containers)
   - Test upload flow with quota checks
   - Test quota recalculation accuracy

3. **Performance Requirements**
   - Quota checks must complete in <5ms (cache hit)
   - Usage updates must be atomic (no lost updates)

### Test Command

```bash
cargo test quota
```

---

## Task 3: Collaborative Editing Backend

### Overview

Implement a real-time collaborative editing backend using Operational Transformation (OT) or CRDT-based conflict resolution. The service should support concurrent edits, presence tracking, and edit history.

### Module Location

Create `src/services/collaboration.rs` and `src/models/operation.rs`.

### Trait Contract

```rust
use async_trait::async_trait;
use thiserror::Error;
use tokio::sync::broadcast;

/// Errors from collaboration operations
#[derive(Error, Debug)]
pub enum CollaborationError {
    #[error("Document not found: {0}")]
    DocumentNotFound(String),

    #[error("Session expired for user: {0}")]
    SessionExpired(String),

    #[error("Operation conflict: {0}")]
    OperationConflict(String),

    #[error("Transform failed: {0}")]
    TransformFailed(String),

    #[error("Unauthorized: user {user_id} cannot access document {doc_id}")]
    Unauthorized { user_id: String, doc_id: String },

    #[error("Channel error: {0}")]
    ChannelError(String),
}

/// Types of edit operations
#[derive(Debug, Clone, PartialEq)]
pub enum OperationType {
    /// Insert text at position
    Insert { position: usize, text: String },
    /// Delete characters from position
    Delete { position: usize, length: usize },
    /// Replace text at position
    Replace { position: usize, length: usize, text: String },
}

/// A single edit operation
#[derive(Debug, Clone)]
pub struct Operation {
    /// Unique operation ID
    pub id: String,
    /// Document this operation applies to
    pub document_id: String,
    /// User who made the edit
    pub user_id: String,
    /// The edit operation
    pub op_type: OperationType,
    /// Server-assigned sequence number
    pub version: u64,
    /// Timestamp of the operation
    pub timestamp: chrono::DateTime<chrono::Utc>,
}

/// User presence information
#[derive(Debug, Clone)]
pub struct UserPresence {
    /// User ID
    pub user_id: String,
    /// Display name
    pub display_name: String,
    /// Cursor position in document
    pub cursor_position: Option<usize>,
    /// Selection range (start, end)
    pub selection: Option<(usize, usize)>,
    /// Last activity timestamp
    pub last_active: chrono::DateTime<chrono::Utc>,
    /// User color for UI highlighting
    pub color: String,
}

/// Document state
#[derive(Debug, Clone)]
pub struct DocumentState {
    /// Document ID
    pub document_id: String,
    /// Current content
    pub content: String,
    /// Current version number
    pub version: u64,
    /// Active users
    pub active_users: Vec<UserPresence>,
    /// Last modified timestamp
    pub last_modified: chrono::DateTime<chrono::Utc>,
}

/// Event broadcast to connected clients
#[derive(Debug, Clone)]
pub enum CollaborationEvent {
    /// An operation was applied
    OperationApplied(Operation),
    /// User joined the document
    UserJoined(UserPresence),
    /// User left the document
    UserLeft { user_id: String },
    /// User presence updated (cursor moved, selection changed)
    PresenceUpdated(UserPresence),
    /// Document was saved
    DocumentSaved { version: u64 },
}

/// Collaboration service for real-time editing
#[async_trait]
pub trait CollaborationService: Send + Sync {
    /// Opens a document for collaborative editing.
    /// Returns the current document state and a subscription for events.
    ///
    /// # Arguments
    /// * `document_id` - The file ID to edit
    /// * `user_id` - The user joining the session
    ///
    /// # Returns
    /// Current document state and event receiver
    async fn join_session(
        &self,
        document_id: &str,
        user_id: &str,
    ) -> Result<(DocumentState, broadcast::Receiver<CollaborationEvent>), CollaborationError>;

    /// Leaves a collaborative editing session.
    async fn leave_session(
        &self,
        document_id: &str,
        user_id: &str,
    ) -> Result<(), CollaborationError>;

    /// Applies an operation from a client.
    /// The operation is transformed against concurrent operations if needed.
    ///
    /// # Arguments
    /// * `document_id` - Target document
    /// * `user_id` - User making the edit
    /// * `op_type` - The edit operation
    /// * `base_version` - Client's version when operation was created
    ///
    /// # Returns
    /// The transformed operation as applied (may differ from input)
    async fn apply_operation(
        &self,
        document_id: &str,
        user_id: &str,
        op_type: OperationType,
        base_version: u64,
    ) -> Result<Operation, CollaborationError>;

    /// Updates user presence (cursor position, selection).
    async fn update_presence(
        &self,
        document_id: &str,
        user_id: &str,
        cursor_position: Option<usize>,
        selection: Option<(usize, usize)>,
    ) -> Result<(), CollaborationError>;

    /// Gets the current state of a document.
    async fn get_document_state(
        &self,
        document_id: &str,
    ) -> Result<DocumentState, CollaborationError>;

    /// Gets the operation history for a document.
    ///
    /// # Arguments
    /// * `document_id` - Target document
    /// * `from_version` - Start version (inclusive)
    /// * `to_version` - End version (exclusive), None for latest
    async fn get_history(
        &self,
        document_id: &str,
        from_version: u64,
        to_version: Option<u64>,
    ) -> Result<Vec<Operation>, CollaborationError>;

    /// Persists the current document state to storage.
    async fn save_document(&self, document_id: &str) -> Result<u64, CollaborationError>;

    /// Lists all active users for a document.
    async fn list_users(&self, document_id: &str) -> Result<Vec<UserPresence>, CollaborationError>;
}
```

### Required Structs and Types

```rust
/// Service implementation
pub struct VaultCollaborationService {
    /// Active document sessions
    sessions: Arc<DashMap<String, DocumentSession>>,
    /// File storage service for persistence
    storage: Arc<StorageService>,
    /// Configuration
    config: CollaborationConfig,
}

/// Per-document session state
pub struct DocumentSession {
    /// Current document content
    content: Arc<RwLock<String>>,
    /// Current version
    version: Arc<std::sync::atomic::AtomicU64>,
    /// Operation log for transformation
    operations: Arc<RwLock<Vec<Operation>>>,
    /// Active users
    users: Arc<DashMap<String, UserPresence>>,
    /// Event broadcaster
    events: broadcast::Sender<CollaborationEvent>,
    /// Last save version
    last_saved_version: Arc<std::sync::atomic::AtomicU64>,
}

/// Configuration
pub struct CollaborationConfig {
    /// Maximum concurrent users per document
    pub max_users_per_document: usize,
    /// Operation history retention count
    pub max_history_operations: usize,
    /// Auto-save interval in seconds
    pub auto_save_interval_seconds: u64,
    /// User presence timeout in seconds
    pub presence_timeout_seconds: u64,
    /// Event channel capacity
    pub event_channel_capacity: usize,
}

/// Operational Transformation engine
pub struct OTEngine;

impl OTEngine {
    /// Transforms operation `a` against operation `b`.
    /// Returns the transformed version of `a` that can be applied after `b`.
    pub fn transform(a: &OperationType, b: &OperationType) -> OperationType {
        // Implementation required
        todo!()
    }

    /// Applies an operation to content, returning the new content.
    pub fn apply(content: &str, op: &OperationType) -> Result<String, CollaborationError> {
        // Implementation required
        todo!()
    }
}
```

### Architectural Patterns to Follow

1. **Event Broadcasting**: Use `tokio::sync::broadcast` for real-time updates
2. **Concurrent State**: Use `DashMap` and `RwLock` for thread-safe session state
3. **Atomic Operations**: Use atomics for version counters
4. **Service Composition**: Depend on `StorageService` for persistence

### Integration Points

- Add WebSocket handler in `handlers/` for real-time communication
- Integrate with `LockManager` for exclusive lock fallback
- Store operation history in database for recovery
- Add collaboration metadata to `FileMetadata`

### Acceptance Criteria

1. **Unit Tests** (create `tests/collaboration_tests.rs`)
   - Test OT transformation for all operation type pairs
   - Test concurrent edits from multiple users
   - Test operation ordering and version management
   - Test presence updates and timeouts
   - Test session join/leave lifecycle
   - Test history retrieval and replay
   - Minimum 25 test cases

2. **Concurrency Tests**
   - Test 10+ concurrent users editing same document
   - Test rapid sequential operations
   - Test network partition simulation (delayed operations)

3. **Correctness Requirements**
   - OT transformations must be commutative: transform(a, b) then apply gives same result as transform(b, a) then apply
   - No lost operations under concurrent edits
   - Document state converges for all users

### Test Command

```bash
cargo test collaboration
```

---

## General Requirements for All Tasks

### Code Style

- Follow Rust 2021 edition idioms
- Use `rustfmt` for formatting
- All public items must have documentation comments
- No `unwrap()` in production code paths (use `?` or explicit error handling)
- Use `#[must_use]` on functions returning important values

### Error Handling

- Define custom error types using `thiserror`
- Implement `From` conversions for error types
- Provide context in error messages

### Testing

- Place tests in `tests/` directory (integration tests)
- Use `#[tokio::test]` for async tests
- Use `mockall` for mocking dependencies
- Use `serial_test` for tests requiring exclusive resources

### Dependencies

Add new dependencies to `Cargo.toml` as needed:
- `aes-gcm` and `chacha20poly1305` for encryption
- `argon2` (already present) for key derivation
- `zeroize` for secure memory clearing

### Running All Tests

```bash
cargo test
```

# VaultFS - Greenfield Development Tasks

## Overview

VaultFS supports three greenfield development tasks that require implementing new modules from scratch. These tasks exercise architectural pattern application, trait-driven design, and integration with existing services while following the VaultFS codebase conventions.

## Environment

- **Language**: Rust
- **Infrastructure**: PostgreSQL (database), Redis (cache), MinIO/S3 (object storage), Axum (web framework), Tokio (async runtime)
- **Difficulty**: Senior (3-6h per task)

## Tasks

### Task 1: Encryption at Rest Service (Greenfield)

Implement a client-side encryption service encrypting files before storage and decrypting on retrieval. Support multiple algorithms (AES-256-GCM, ChaCha20-Poly1305) and per-user key management with rotation.

**Key Interfaces**:
- `EncryptionService` trait with `encrypt()`, `decrypt()`, `initialize_user_key()`, `rotate_key()`, `has_key()` methods
- `EncryptionMetadata` struct storing algorithm, IV, key version, auth tag
- `VaultEncryptionService` implementation with `Arc<RwLock<HashMap>>` key storage and `EncryptionConfig`

**Integration**: Add to `AppState`, integrate with `StorageService` upload/download, store metadata in `FileMetadata.custom_fields`, use `zeroize` crate for secure memory clearing.

**Acceptance Criteria**: Round-trip encryption/decryption works for both algorithms, key initialization and rotation functional, error cases handled (wrong passphrase, missing key, corrupted data), concurrent key access safe, 15+ unit tests, edge cases covered (empty files, large files >100MB, special characters), keys never plaintext, constant-time authentication tag comparison, cryptographically random IVs, memory zeroization on cleanup.

### Task 2: File Quota Manager (Greenfield)

Implement quota management tracking storage usage per user and enforcing limits. Support soft limits (warnings), hard limits (rejections), quota inheritance for shared folders, and per-tier configuration.

**Key Interfaces**:
- `QuotaService` trait with `check_upload()`, `record_upload()`, `record_deletion()`, `get_usage()`, `get_tier()`, `set_tier()`, `recalculate_usage()`, `list_users_near_limit()` methods
- `UsageStats` struct with bytes_used, file_count, quota_limit, percent_used, usage breakdown
- `QuotaTier` struct with tier name, storage limit, max file size, max file count, soft limit percent
- `VaultQuotaService` with `DashMap` usage cache and `QuotaRepository` for persistence
- `QuotaRepository` trait for database operations

**Integration**: Hook into upload handlers for pre-check, hook into delete handlers for usage updates, add quota info to `FileMetadata` responses, add `/api/quota` endpoint.

**Acceptance Criteria**: Upload check works across quota states, usage recording and deletion accurate, tier upgrades/downgrades functional, soft limit warnings trigger correctly, cache expiration works, concurrent updates handle race conditions, 20+ unit tests, integration tests with actual database, quota checks <5ms (cache hit), atomic usage updates.

### Task 3: Collaborative Editing Backend (Greenfield)

Implement real-time collaborative editing using Operational Transformation (OT) with concurrent edit support, presence tracking, and edit history.

**Key Interfaces**:
- `CollaborationService` trait with `join_session()`, `leave_session()`, `apply_operation()`, `update_presence()`, `get_document_state()`, `get_history()`, `save_document()`, `list_users()` methods
- `Operation` struct with id, document_id, user_id, op_type, version, timestamp
- `OperationType` enum: Insert, Delete, Replace
- `DocumentState` struct with content, version, active_users, last_modified
- `UserPresence` struct with cursor position, selection range, last activity, color
- `VaultCollaborationService` with `DashMap<String, DocumentSession>` for active sessions
- `DocumentSession` struct managing content, version, operations log, users, event broadcaster
- `OTEngine` with `transform()` and `apply()` methods for Operational Transformation

**Integration**: Add WebSocket handler in `handlers/`, integrate with `LockManager` for exclusive lock fallback, store operation history in database, add collaboration metadata to `FileMetadata`.

**Acceptance Criteria**: OT transformation works for all operation pairs, concurrent edits from 10+ users, operation ordering and version management correct, presence updates and timeouts work, session join/leave lifecycle functional, history retrieval and replay accurate, 25+ unit tests, concurrency tests with rapid sequential operations, OT commutative property verified (transform(a,b) then apply = transform(b,a) then apply), no lost operations, document state converges.

## Getting Started

```bash
# Start infrastructure
docker compose up -d

# Run tests
cargo test

# Run task-specific tests
cargo test encryption
cargo test quota
cargo test collaboration
```

## Success Criteria

Implementation meets the acceptance criteria defined in [TASKS_GREENFIELD.md](./TASKS_GREENFIELD.md). All code follows Rust 2021 idioms, includes comprehensive documentation, uses proper error handling with `thiserror`, and includes sufficient test coverage (15-25+ tests per module).

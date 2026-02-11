# DocuVault - Alternative Tasks

## Overview

Five alternative development tasks for the DocuVault enterprise document management platform covering workflow automation, system refactoring, performance optimization, API extension, and infrastructure migration.

## Environment

- **Language**: Java 21
- **Framework**: Spring Boot 3.2, Spring Data JPA
- **Infrastructure**: PostgreSQL 16, Redis 7
- **Difficulty**: Senior (2-4h per task)

## Tasks

### Task 1: Document Workflow Automation (Feature Development)

Implement a document workflow automation system that enables multi-stage approval processes for sensitive documents. The workflow engine must integrate with the existing document versioning system, create new versions on stage transitions, send notifications to approvers, and maintain an audit trail of all workflow actions. Workflow templates should be reusable across document types with support for escalation timeouts and auto-approval rules.

### Task 2: Permission System Consolidation (Refactoring)

Consolidate scattered permission-related logic from DocumentService, ShareService, and SearchService into a dedicated PermissionService. Implement a clean separation between permission storage, evaluation, and enforcement. The refactored system should support permission inheritance from folders to documents and provide an extensible foundation for future permission types while maintaining backward compatibility with existing REST API endpoints.

### Task 3: Search Performance Optimization (Performance Optimization)

Optimize DocuVault's search functionality to eliminate full table scans and in-memory pagination. Replace with database-level pagination, implement search result caching with proper invalidation, and add composite database indexes. The optimized search must support sorting by relevance/date/size, maintain sub-second response times for 100,000+ document repositories, and use efficient metadata filtering with JPA Specifications.

### Task 4: Bulk Operations API (API Extension)

Create a bulk operations API that enables batch creation, update, deletion, sharing, and tagging of documents in single transactional requests. Implement configurable chunk processing to handle large batches, support rollback-on-failure or continue-on-failure semantics, and return detailed per-item success/failure status. The API must respect permission checks and support progress tracking for long-running operations.

### Task 5: Document Storage Provider Migration (Migration)

Abstract the document storage layer behind a StorageProvider interface and implement migration from local filesystem to S3-compatible cloud storage. Support hybrid state where documents exist in both locations, implement lazy migration on first access, and add background batch migration. The implementation must update checksum validation for cloud storage, add retry logic with exponential backoff, and maintain existing API contracts transparently.

## Getting Started

```bash
cd /Users/amit/projects/terminal-bench-envs/java/docuvault
docker compose up -d
mvn test
```

## Success Criteria

Implementation meets the acceptance criteria defined in [TASKS_ALTERNATIVE.md](./TASKS_ALTERNATIVE.md).

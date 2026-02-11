# DocuVault - Greenfield Implementation Tasks

## Overview

Three greenfield implementation tasks for extending DocuVault's capabilities with new subsystems. Each task requires building a new module from scratch while following existing architectural patterns for Spring services, JPA entities, and repository interfaces.

## Environment

- **Language**: Java 21
- **Framework**: Spring Boot 3.2, Spring Data JPA
- **Infrastructure**: PostgreSQL 16, Redis 7
- **Difficulty**: Senior (2-4h per task)

## Tasks

### Task 1: Document Comparison Service (New Service)

Implement a service that compares two document versions and produces a structured diff report showing additions, deletions, modifications, and unchanged content. The service must calculate similarity scores, find similar versions, and support comparison between different documents. Create model classes for ComparisonResult with DiffChunk analysis, metadata tracking, and processing timestamps. Implement caching for frequently compared versions and integrate with the version management system.

**Key Interfaces**:
- `DocumentComparisonService` with methods for version comparison, similarity calculation, and finding similar versions
- `ComparisonResult` containing diff chunks and metadata
- `DiffChunk` with type, line numbers, and content before/after
- `ComparisonMetadata` tracking added/deleted/modified line counts and processing time

### Task 2: Document Retention Policy Engine (New Service)

Implement a retention policy engine that manages document lifecycle based on configurable rules. Policies trigger actions (archive, delete, flag for review, extend retention, notify owner) based on document age, type, or custom metadata. Create entities for RetentionPolicy with pattern matching, priority ordering, and metadata conditions. Support CRUD operations, policy evaluation against documents, batch evaluation, scheduled action execution, and content type pattern matching with priority-based action selection.

**Key Interfaces**:
- `RetentionPolicyService` with policy CRUD, evaluation, and action execution
- `RetentionPolicy` entity with content type patterns, retention days, and priority
- `PolicyEvaluationResult` containing matching policies and recommended actions
- `ScheduledRetentionAction` tracking deferred execution and results

### Task 3: Document OCR Processing Pipeline (New Service)

Implement an asynchronous OCR processing pipeline that extracts text from image-based documents (PDFs, images) for full-text search indexing. Support job submission, status tracking, batch processing, job cancellation, and retry logic for failed jobs. Create entities for OcrJob tracking status, priority, and configuration with support for per-page text extraction and confidence scoring. Integrate with the search service for full-text indexing and use a dedicated thread pool for async processing.

**Key Interfaces**:
- `OcrProcessingService` with job submission, status queries, result retrieval, and cancellation
- `OcrJob` entity with status tracking, priority, and retry logic
- `OcrJobStatus` enum for PENDING, IN_PROGRESS, COMPLETED, FAILED, CANCELLED, RETRYING
- `OcrResult` containing extracted text, page count, confidence score, and processing time
- `OcrConfiguration` for language, image enhancement, table detection, and page selection

## Getting Started

```bash
cd /Users/amit/projects/terminal-bench-envs/java/docuvault
docker compose up -d
mvn test
```

## Success Criteria

Implementation meets the acceptance criteria defined in [TASKS_GREENFIELD.md](./TASKS_GREENFIELD.md).

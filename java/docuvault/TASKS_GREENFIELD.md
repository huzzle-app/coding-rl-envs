# DocuVault - Greenfield Implementation Tasks

This document contains greenfield implementation tasks for extending DocuVault's document management capabilities. Each task requires implementing a new module from scratch while following the existing architectural patterns.

**Test Command**: `mvn test`

---

## Task 1: Document Comparison Service

### Overview

Implement a service that compares two document versions and produces a structured diff report. This is essential for auditing changes, reviewing document history, and providing users with visibility into what changed between versions.

### Interface Contract

Create the following interface at `src/main/java/com/docuvault/service/DocumentComparisonService.java`:

```java
package com.docuvault.service;

import com.docuvault.model.Document;
import com.docuvault.model.DocumentVersion;
import com.docuvault.model.comparison.ComparisonResult;
import com.docuvault.model.comparison.DiffChunk;

import java.util.List;
import java.util.Optional;

/**
 * Service for comparing document versions and generating diff reports.
 *
 * <p>This service provides functionality to compare two versions of a document
 * and produce a structured representation of the differences. It supports
 * both text-based content comparison and metadata comparison.</p>
 *
 * <p>Thread Safety: Implementations must be thread-safe and suitable for
 * use in a concurrent web application environment.</p>
 */
public interface DocumentComparisonService {

    /**
     * Compares two versions of a document and returns a detailed diff report.
     *
     * @param documentId the ID of the document to compare versions for
     * @param fromVersion the source version number (older)
     * @param toVersion the target version number (newer)
     * @return a ComparisonResult containing the structured diff
     * @throws IllegalArgumentException if version numbers are invalid or equal
     * @throws DocumentNotFoundException if the document does not exist
     * @throws VersionNotFoundException if either version does not exist
     */
    ComparisonResult compareVersions(Long documentId, Integer fromVersion, Integer toVersion);

    /**
     * Compares the current document state with a specific historical version.
     *
     * @param documentId the ID of the document
     * @param historicalVersion the historical version number to compare against
     * @return a ComparisonResult showing changes from historical to current
     * @throws DocumentNotFoundException if the document does not exist
     * @throws VersionNotFoundException if the version does not exist
     */
    ComparisonResult compareWithCurrent(Long documentId, Integer historicalVersion);

    /**
     * Compares two different documents (e.g., for duplicate detection).
     *
     * @param documentId1 the ID of the first document
     * @param documentId2 the ID of the second document
     * @return a ComparisonResult showing differences between documents
     * @throws DocumentNotFoundException if either document does not exist
     */
    ComparisonResult compareDocuments(Long documentId1, Long documentId2);

    /**
     * Generates individual diff chunks for line-by-line comparison.
     *
     * @param content1 the first content string
     * @param content2 the second content string
     * @return a list of DiffChunk objects representing individual changes
     */
    List<DiffChunk> generateDiffChunks(String content1, String content2);

    /**
     * Calculates a similarity score between two document versions.
     *
     * @param documentId the document ID
     * @param version1 the first version number
     * @param version2 the second version number
     * @return a similarity score between 0.0 (completely different) and 1.0 (identical)
     */
    double calculateSimilarity(Long documentId, Integer version1, Integer version2);

    /**
     * Finds the most similar version to a given version.
     *
     * @param documentId the document ID
     * @param targetVersion the version to find similar versions for
     * @param limit maximum number of similar versions to return
     * @return list of version numbers ordered by similarity (most similar first)
     */
    List<Integer> findSimilarVersions(Long documentId, Integer targetVersion, int limit);
}
```

### Required Classes/Models

Create the following model classes in `src/main/java/com/docuvault/model/comparison/`:

1. **ComparisonResult.java**
   - `Long documentId` - the document being compared
   - `Integer fromVersion` - source version number
   - `Integer toVersion` - target version number
   - `List<DiffChunk> chunks` - list of individual differences
   - `ComparisonMetadata metadata` - summary statistics
   - `LocalDateTime comparedAt` - timestamp of comparison

2. **DiffChunk.java**
   - `DiffType type` - enum: ADDITION, DELETION, MODIFICATION, UNCHANGED
   - `int startLine` - starting line number in source
   - `int endLine` - ending line number in source
   - `String originalContent` - content from source version
   - `String modifiedContent` - content from target version
   - `int targetStartLine` - starting line in target

3. **ComparisonMetadata.java**
   - `int totalLinesAdded` - count of added lines
   - `int totalLinesDeleted` - count of deleted lines
   - `int totalLinesModified` - count of modified lines
   - `double similarityScore` - 0.0 to 1.0
   - `long processingTimeMs` - time taken to compute diff

4. **DiffType.java** (enum)
   - ADDITION, DELETION, MODIFICATION, UNCHANGED

### Architectural Requirements

1. **Follow Spring patterns**: Use `@Service` annotation, constructor injection with `@Autowired`
2. **Transaction management**: Use `@Transactional(readOnly = true)` for read operations
3. **Caching**: Implement `@Cacheable` for frequently compared versions using cache name `"comparisons"`
4. **Logging**: Use SLF4J logger following the pattern in `DocumentService`
5. **Exception handling**: Create custom exceptions extending `RuntimeException`

### Acceptance Criteria

1. **Unit Tests** (create in `src/test/java/com/docuvault/unit/DocumentComparisonServiceTest.java`):
   - Test version comparison with additions only
   - Test version comparison with deletions only
   - Test version comparison with mixed changes
   - Test similarity score calculation (0.0 for completely different, 1.0 for identical)
   - Test invalid version number handling
   - Test document not found handling
   - Test comparing same version throws IllegalArgumentException

2. **Integration Tests** (create in `src/test/java/com/docuvault/integration/DocumentComparisonIntegrationTest.java`):
   - Test comparison with persisted documents and versions
   - Test cache behavior for repeated comparisons
   - Test transaction boundaries

3. **Coverage Requirements**:
   - Minimum 80% line coverage for the service implementation
   - All public methods must have at least one test

4. **Integration Points**:
   - Inject `DocumentRepository` for document/version retrieval
   - Integrate with `VersionService` for version management
   - Results should be compatible with `NotificationService` for change notifications

---

## Task 2: Document Retention Policy Engine

### Overview

Implement a retention policy engine that manages document lifecycle based on configurable rules. Documents can be automatically archived, flagged for review, or scheduled for deletion based on age, document type, or custom metadata.

### Interface Contract

Create the following interface at `src/main/java/com/docuvault/service/RetentionPolicyService.java`:

```java
package com.docuvault.service;

import com.docuvault.model.Document;
import com.docuvault.model.retention.RetentionPolicy;
import com.docuvault.model.retention.RetentionAction;
import com.docuvault.model.retention.PolicyEvaluationResult;

import java.time.LocalDateTime;
import java.util.List;
import java.util.Optional;

/**
 * Service for managing document retention policies and executing retention actions.
 *
 * <p>The retention policy engine allows organizations to define rules for
 * document lifecycle management. Policies can trigger actions such as archival,
 * deletion, or review flags based on document age, type, or metadata.</p>
 *
 * <p>Thread Safety: All policy evaluation methods must be thread-safe.
 * Policy modifications should use optimistic locking.</p>
 */
public interface RetentionPolicyService {

    /**
     * Creates a new retention policy.
     *
     * @param policy the policy to create
     * @return the created policy with generated ID
     * @throws PolicyValidationException if the policy configuration is invalid
     * @throws DuplicatePolicyException if a policy with the same name exists
     */
    RetentionPolicy createPolicy(RetentionPolicy policy);

    /**
     * Updates an existing retention policy.
     *
     * @param policyId the ID of the policy to update
     * @param policy the updated policy data
     * @return the updated policy
     * @throws PolicyNotFoundException if the policy does not exist
     * @throws PolicyValidationException if the updated configuration is invalid
     */
    RetentionPolicy updatePolicy(Long policyId, RetentionPolicy policy);

    /**
     * Deletes a retention policy.
     *
     * @param policyId the ID of the policy to delete
     * @throws PolicyNotFoundException if the policy does not exist
     * @throws PolicyInUseException if the policy is currently applied to documents
     */
    void deletePolicy(Long policyId);

    /**
     * Retrieves a policy by ID.
     *
     * @param policyId the policy ID
     * @return an Optional containing the policy if found
     */
    Optional<RetentionPolicy> getPolicy(Long policyId);

    /**
     * Lists all active retention policies.
     *
     * @return list of all active policies
     */
    List<RetentionPolicy> listActivePolicies();

    /**
     * Evaluates a single document against all applicable policies.
     *
     * @param documentId the document to evaluate
     * @return the evaluation result including recommended actions
     * @throws DocumentNotFoundException if the document does not exist
     */
    PolicyEvaluationResult evaluateDocument(Long documentId);

    /**
     * Evaluates all documents and returns those requiring action.
     *
     * @param actionType filter by specific action type, or null for all
     * @param limit maximum number of results
     * @return list of evaluation results for documents requiring action
     */
    List<PolicyEvaluationResult> evaluateAllDocuments(RetentionAction actionType, int limit);

    /**
     * Executes the recommended retention action for a document.
     *
     * @param documentId the document to act upon
     * @param action the action to execute
     * @param executedBy the user performing the action
     * @throws DocumentNotFoundException if the document does not exist
     * @throws ActionNotAllowedException if the action is not permitted
     */
    void executeRetentionAction(Long documentId, RetentionAction action, Long executedBy);

    /**
     * Schedules a document for future retention action.
     *
     * @param documentId the document to schedule
     * @param action the action to schedule
     * @param scheduledFor when the action should be executed
     * @param scheduledBy the user scheduling the action
     * @return the scheduled action ID
     */
    Long scheduleRetentionAction(Long documentId, RetentionAction action,
                                  LocalDateTime scheduledFor, Long scheduledBy);

    /**
     * Finds all policies applicable to a specific document type.
     *
     * @param contentType the document content type (e.g., "application/pdf")
     * @return list of applicable policies
     */
    List<RetentionPolicy> findPoliciesByContentType(String contentType);

    /**
     * Calculates the retention expiry date for a document based on policies.
     *
     * @param documentId the document ID
     * @return the calculated expiry date, or empty if no policy applies
     */
    Optional<LocalDateTime> calculateExpiryDate(Long documentId);
}
```

### Required Classes/Models

Create the following in `src/main/java/com/docuvault/model/retention/`:

1. **RetentionPolicy.java** (JPA Entity)
   - `Long id` - primary key
   - `String name` - unique policy name
   - `String description` - policy description
   - `String contentTypePattern` - regex pattern for content types (e.g., "application/pdf|image/.*")
   - `Integer retentionDays` - days to retain before action
   - `RetentionAction action` - action to take when policy triggers
   - `Boolean isActive` - whether policy is enabled
   - `Integer priority` - evaluation order (lower = higher priority)
   - `LocalDateTime createdAt` - creation timestamp
   - `LocalDateTime updatedAt` - last update timestamp
   - `Long createdBy` - user ID who created the policy
   - `Map<String, String> metadataConditions` - additional conditions as key-value pairs

2. **RetentionAction.java** (enum)
   - `ARCHIVE` - move to archive storage
   - `DELETE` - permanently delete
   - `FLAG_FOR_REVIEW` - mark for manual review
   - `EXTEND` - extend retention period
   - `NOTIFY_OWNER` - send notification to document owner

3. **PolicyEvaluationResult.java**
   - `Long documentId` - the evaluated document
   - `String documentName` - document name for display
   - `List<RetentionPolicy> matchingPolicies` - policies that match this document
   - `RetentionAction recommendedAction` - highest priority action
   - `LocalDateTime actionDueDate` - when action should be taken
   - `String reason` - human-readable explanation
   - `Boolean isOverdue` - whether the action is past due

4. **ScheduledRetentionAction.java** (JPA Entity)
   - `Long id` - primary key
   - `Long documentId` - target document
   - `RetentionAction action` - scheduled action
   - `LocalDateTime scheduledFor` - execution time
   - `Long scheduledBy` - user who scheduled
   - `Boolean isExecuted` - whether action was executed
   - `LocalDateTime executedAt` - actual execution time
   - `String executionResult` - success/failure details

### Repository Interface

Create `src/main/java/com/docuvault/repository/RetentionPolicyRepository.java`:

```java
package com.docuvault.repository;

import com.docuvault.model.retention.RetentionPolicy;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.stereotype.Repository;

import java.util.List;
import java.util.Optional;

@Repository
public interface RetentionPolicyRepository extends JpaRepository<RetentionPolicy, Long> {

    Optional<RetentionPolicy> findByName(String name);

    List<RetentionPolicy> findByIsActiveTrueOrderByPriorityAsc();

    @Query("SELECT p FROM RetentionPolicy p WHERE p.isActive = true AND :contentType REGEXP p.contentTypePattern ORDER BY p.priority")
    List<RetentionPolicy> findMatchingPolicies(@Param("contentType") String contentType);
}
```

### Architectural Requirements

1. **JPA Entities**: Use proper annotations (`@Entity`, `@Table`, `@Column`, etc.)
2. **Optimistic Locking**: Add `@Version` field to `RetentionPolicy` entity
3. **Validation**: Use Jakarta validation annotations (`@NotNull`, `@Size`, etc.)
4. **Async Processing**: Use `@Async` for batch evaluation methods (follow proxy pattern from existing code)
5. **Transactions**: Use `@Transactional` appropriately for write operations

### Acceptance Criteria

1. **Unit Tests** (create in `src/test/java/com/docuvault/unit/RetentionPolicyServiceTest.java`):
   - Test policy CRUD operations
   - Test policy validation (reject invalid retention days, empty names)
   - Test document evaluation with single matching policy
   - Test document evaluation with multiple policies (priority ordering)
   - Test action execution for each action type
   - Test scheduling and execution of scheduled actions
   - Test content type pattern matching

2. **Integration Tests** (create in `src/test/java/com/docuvault/integration/RetentionPolicyIntegrationTest.java`):
   - Test policy persistence and retrieval
   - Test document lifecycle with retention policy
   - Test concurrent policy updates (optimistic locking)
   - Test scheduled action execution

3. **Coverage Requirements**:
   - Minimum 80% line coverage
   - 100% coverage for policy evaluation logic

4. **Integration Points**:
   - Inject `DocumentRepository` for document access
   - Use `NotificationService` for `NOTIFY_OWNER` action
   - Integrate with `SearchService` for batch document evaluation

---

## Task 3: Document OCR Processing Pipeline

### Overview

Implement an OCR (Optical Character Recognition) processing pipeline that extracts text content from image-based documents (PDFs, images). The pipeline should support asynchronous processing, status tracking, and integration with the search service for full-text indexing.

### Interface Contract

Create the following interface at `src/main/java/com/docuvault/service/OcrProcessingService.java`:

```java
package com.docuvault.service;

import com.docuvault.model.Document;
import com.docuvault.model.ocr.OcrJob;
import com.docuvault.model.ocr.OcrResult;
import com.docuvault.model.ocr.OcrJobStatus;
import com.docuvault.model.ocr.OcrConfiguration;

import java.util.List;
import java.util.Optional;
import java.util.concurrent.CompletableFuture;

/**
 * Service for processing documents through OCR to extract text content.
 *
 * <p>This service manages the OCR pipeline including job submission,
 * status tracking, result retrieval, and integration with the search
 * index for full-text search capabilities.</p>
 *
 * <p>Thread Safety: All methods are thread-safe. Job processing occurs
 * asynchronously on a dedicated thread pool.</p>
 */
public interface OcrProcessingService {

    /**
     * Submits a document for OCR processing.
     *
     * @param documentId the document to process
     * @param config optional configuration for OCR processing
     * @return the created OCR job with tracking ID
     * @throws DocumentNotFoundException if the document does not exist
     * @throws UnsupportedContentTypeException if the document type is not supported
     * @throws DuplicateJobException if an active job already exists for this document
     */
    OcrJob submitForProcessing(Long documentId, OcrConfiguration config);

    /**
     * Submits multiple documents for batch OCR processing.
     *
     * @param documentIds list of document IDs to process
     * @param config shared configuration for all documents
     * @return list of created OCR jobs
     */
    List<OcrJob> submitBatchForProcessing(List<Long> documentIds, OcrConfiguration config);

    /**
     * Retrieves the current status of an OCR job.
     *
     * @param jobId the job ID
     * @return the current job status
     * @throws JobNotFoundException if the job does not exist
     */
    OcrJob getJobStatus(Long jobId);

    /**
     * Retrieves the OCR result for a completed job.
     *
     * @param jobId the job ID
     * @return the OCR result if available
     * @throws JobNotFoundException if the job does not exist
     * @throws JobNotCompleteException if the job has not finished
     */
    OcrResult getJobResult(Long jobId);

    /**
     * Cancels a pending or in-progress OCR job.
     *
     * @param jobId the job to cancel
     * @return true if cancellation was successful
     * @throws JobNotFoundException if the job does not exist
     * @throws JobNotCancellableException if the job has already completed
     */
    boolean cancelJob(Long jobId);

    /**
     * Lists all OCR jobs for a specific document.
     *
     * @param documentId the document ID
     * @return list of OCR jobs ordered by creation date descending
     */
    List<OcrJob> getJobsForDocument(Long documentId);

    /**
     * Lists all jobs with a specific status.
     *
     * @param status the status to filter by
     * @param limit maximum number of results
     * @return list of jobs with the specified status
     */
    List<OcrJob> getJobsByStatus(OcrJobStatus status, int limit);

    /**
     * Retries a failed OCR job.
     *
     * @param jobId the failed job to retry
     * @return the new job created for the retry
     * @throws JobNotFoundException if the original job does not exist
     * @throws InvalidJobStateException if the job did not fail
     */
    OcrJob retryFailedJob(Long jobId);

    /**
     * Processes a job asynchronously and returns a future with the result.
     *
     * @param job the job to process
     * @return a CompletableFuture that completes with the OCR result
     */
    CompletableFuture<OcrResult> processAsync(OcrJob job);

    /**
     * Extracts text from document content synchronously.
     *
     * @param documentId the document to extract text from
     * @return the extracted text content
     * @throws DocumentNotFoundException if the document does not exist
     * @throws OcrProcessingException if text extraction fails
     */
    String extractText(Long documentId);

    /**
     * Checks if a document type is supported for OCR.
     *
     * @param contentType the MIME type to check
     * @return true if the content type is supported
     */
    boolean isContentTypeSupported(String contentType);

    /**
     * Gets the list of supported content types.
     *
     * @return list of supported MIME types
     */
    List<String> getSupportedContentTypes();

    /**
     * Updates the search index with extracted OCR text.
     *
     * @param documentId the document to index
     * @param extractedText the OCR-extracted text
     */
    void updateSearchIndex(Long documentId, String extractedText);
}
```

### Required Classes/Models

Create the following in `src/main/java/com/docuvault/model/ocr/`:

1. **OcrJob.java** (JPA Entity)
   - `Long id` - primary key
   - `Long documentId` - target document
   - `OcrJobStatus status` - current job status
   - `Integer priority` - processing priority (1-10)
   - `LocalDateTime submittedAt` - submission timestamp
   - `LocalDateTime startedAt` - processing start time
   - `LocalDateTime completedAt` - completion time
   - `Long submittedBy` - user who submitted
   - `String errorMessage` - error details if failed
   - `Integer retryCount` - number of retry attempts
   - `Integer maxRetries` - maximum allowed retries
   - `OcrConfiguration configuration` - job configuration (embedded)

2. **OcrJobStatus.java** (enum)
   - `PENDING` - waiting to be processed
   - `IN_PROGRESS` - currently being processed
   - `COMPLETED` - successfully completed
   - `FAILED` - processing failed
   - `CANCELLED` - cancelled by user
   - `RETRYING` - scheduled for retry

3. **OcrResult.java** (JPA Entity)
   - `Long id` - primary key
   - `Long jobId` - associated job
   - `Long documentId` - processed document
   - `String extractedText` - the OCR text content
   - `Integer pageCount` - number of pages processed
   - `Double confidence` - OCR confidence score (0.0-1.0)
   - `String language` - detected language
   - `Long processingTimeMs` - processing duration
   - `LocalDateTime createdAt` - result creation time
   - `Map<Integer, String> pageTexts` - text by page number (for multi-page docs)

4. **OcrConfiguration.java** (Embeddable)
   - `String language` - target language hint (e.g., "en", "auto")
   - `Boolean enhanceImages` - apply image enhancement before OCR
   - `Integer dpi` - target DPI for image processing
   - `Boolean detectTables` - attempt table structure detection
   - `Boolean detectHandwriting` - enable handwriting recognition
   - `List<Integer> pagesToProcess` - specific pages (null = all pages)

### Repository Interfaces

Create repository interfaces:

```java
// src/main/java/com/docuvault/repository/OcrJobRepository.java
@Repository
public interface OcrJobRepository extends JpaRepository<OcrJob, Long> {
    List<OcrJob> findByDocumentIdOrderBySubmittedAtDesc(Long documentId);
    List<OcrJob> findByStatusOrderByPriorityDescSubmittedAtAsc(OcrJobStatus status, Pageable pageable);
    Optional<OcrJob> findByDocumentIdAndStatusIn(Long documentId, List<OcrJobStatus> statuses);
    @Query("SELECT j FROM OcrJob j WHERE j.status = 'PENDING' ORDER BY j.priority DESC, j.submittedAt ASC")
    List<OcrJob> findNextPendingJobs(Pageable pageable);
}

// src/main/java/com/docuvault/repository/OcrResultRepository.java
@Repository
public interface OcrResultRepository extends JpaRepository<OcrResult, Long> {
    Optional<OcrResult> findByJobId(Long jobId);
    Optional<OcrResult> findByDocumentId(Long documentId);
}
```

### Architectural Requirements

1. **Async Processing**: Use `@Async` with proper exception handling (learn from bug A3 in ShareService)
2. **Thread Pool**: Configure a dedicated `TaskExecutor` for OCR processing in `AppConfig`
3. **Rate Limiting**: Implement processing queue with configurable concurrency
4. **Caching**: Cache supported content types check
5. **Event Publishing**: Publish events on job completion for integration with other services
6. **Transactions**: Separate read and write transaction scopes appropriately

### Acceptance Criteria

1. **Unit Tests** (create in `src/test/java/com/docuvault/unit/OcrProcessingServiceTest.java`):
   - Test job submission and status tracking
   - Test content type validation
   - Test job cancellation
   - Test retry logic for failed jobs
   - Test configuration handling
   - Test async processing completion
   - Test exception handling (should not swallow exceptions)

2. **Integration Tests** (create in `src/test/java/com/docuvault/integration/OcrProcessingIntegrationTest.java`):
   - Test end-to-end job processing
   - Test search index update after OCR
   - Test concurrent job submission
   - Test job persistence and recovery

3. **Concurrency Tests** (create in `src/test/java/com/docuvault/concurrency/OcrConcurrencyTest.java`):
   - Test thread safety of job status updates
   - Test concurrent cancellation
   - Test processing queue under load

4. **Coverage Requirements**:
   - Minimum 80% line coverage
   - All async paths must have tests

5. **Integration Points**:
   - Inject `DocumentRepository` and `DocumentService` for document access
   - Integrate with `SearchService` for full-text indexing
   - Use `NotificationService` to notify users on job completion
   - Integrate with `FileUtils` for file path handling

---

## General Requirements for All Tasks

### Code Style

1. Follow existing package structure under `com.docuvault`
2. Use constructor injection with `@Autowired` (not field injection where possible)
3. Add comprehensive Javadoc comments matching the interface contracts
4. Use SLF4J for logging with appropriate log levels
5. Follow the naming conventions visible in existing code

### Testing Patterns

1. Use JUnit 5 annotations (`@Test`, `@BeforeEach`, `@DisplayName`)
2. Use Spring Boot Test (`@SpringBootTest`, `@MockBean`, `@Autowired`)
3. Use H2 in-memory database for integration tests
4. Follow the test package structure: `unit`, `integration`, `concurrency`

### Exception Handling

Create custom exceptions in `src/main/java/com/docuvault/exception/`:
- Extend `RuntimeException` for unchecked exceptions
- Include meaningful error messages
- Consider creating a base `DocuVaultException` class

### Database Migrations

If creating new JPA entities, add Flyway migration scripts in `src/main/resources/db/migration/` following the naming pattern `V{version}__{description}.sql`.

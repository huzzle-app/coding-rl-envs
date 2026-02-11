# MindVault Greenfield Tasks

These tasks require implementing NEW modules from scratch. Each task builds upon existing MindVault infrastructure and must follow established architectural patterns.

## Prerequisites

Before starting any greenfield task:
1. Ensure the existing test suite passes: `./gradlew test`
2. Review existing service patterns in `/documents`, `/search`, `/graph`, `/embeddings`
3. Understand the shared infrastructure in `/shared` (EventBus, models, serialization)

---

## Task 1: Knowledge Gap Detector

### Overview

Implement a service that analyzes a user's knowledge base to identify gaps, missing connections, and potential areas for expansion. The detector compares document coverage against a reference ontology or knowledge domain and suggests topics the user should explore.

### Module Location

```
mindvault/
  gapdetector/
    src/main/kotlin/com/mindvault/gapdetector/
      GapDetectorService.kt
      GapDetectorModels.kt
    src/test/kotlin/com/mindvault/gapdetector/
      GapDetectorTests.kt
    build.gradle.kts
```

### Interface Contract

```kotlin
package com.mindvault.gapdetector

import kotlinx.coroutines.flow.Flow
import kotlinx.serialization.Serializable
import java.time.Instant

/**
 * Service for detecting knowledge gaps in a user's document collection.
 *
 * Analyzes document content, graph connections, and embeddings to identify:
 * - Missing topics within a domain
 * - Orphaned documents with no connections
 * - Weak concept areas with shallow coverage
 * - Suggested topics based on existing knowledge patterns
 */
interface KnowledgeGapDetector {

    /**
     * Analyzes a user's knowledge base and returns identified gaps.
     *
     * @param userId The user whose knowledge base to analyze
     * @param domainId Optional domain to scope the analysis (null for full analysis)
     * @param options Configuration for gap detection thresholds
     * @return Analysis result containing detected gaps and recommendations
     * @throws AnalysisException if the knowledge base cannot be analyzed
     */
    suspend fun analyzeKnowledgeGaps(
        userId: String,
        domainId: String? = null,
        options: GapDetectionOptions = GapDetectionOptions()
    ): GapAnalysisResult

    /**
     * Streams gap detection updates as documents are added or modified.
     *
     * @param userId The user to monitor
     * @return Flow of incremental gap updates
     */
    fun gapUpdatesFlow(userId: String): Flow<GapUpdate>

    /**
     * Computes coverage metrics for a specific topic within the knowledge base.
     *
     * @param userId The user whose coverage to compute
     * @param topicId The topic/concept ID to measure coverage for
     * @return Coverage score and related documents
     */
    suspend fun computeTopicCoverage(
        userId: String,
        topicId: String
    ): TopicCoverage

    /**
     * Identifies orphaned documents that have no meaningful connections.
     *
     * @param userId The user whose documents to scan
     * @param minConnectionThreshold Minimum connections for a document to be considered integrated
     * @return List of orphaned documents with suggestions for integration
     */
    suspend fun findOrphanedDocuments(
        userId: String,
        minConnectionThreshold: Int = 2
    ): List<OrphanedDocument>

    /**
     * Generates topic recommendations based on existing knowledge patterns.
     *
     * @param userId The user to generate recommendations for
     * @param count Maximum number of recommendations to return
     * @return Ranked list of suggested topics with relevance scores
     */
    suspend fun suggestTopics(
        userId: String,
        count: Int = 10
    ): List<TopicSuggestion>
}
```

### Required Data Classes

```kotlin
package com.mindvault.gapdetector

import kotlinx.serialization.Serializable
import java.time.Instant

@Serializable
data class GapDetectionOptions(
    val coverageThreshold: Double = 0.7,
    val minDocumentsPerTopic: Int = 3,
    val includeOrphanAnalysis: Boolean = true,
    val maxGapsToReturn: Int = 50,
    val depthLimit: Int = 3
)

@Serializable
data class GapAnalysisResult(
    val userId: String,
    val analyzedAt: Long, // epochMillis for serialization
    val totalDocuments: Int,
    val totalConcepts: Int,
    val overallCoverageScore: Double,
    val identifiedGaps: List<KnowledgeGap>,
    val orphanedDocuments: List<OrphanedDocument>,
    val recommendations: List<TopicSuggestion>
)

@Serializable
sealed class KnowledgeGap {
    abstract val gapId: String
    abstract val severity: GapSeverity
    abstract val description: String

    @Serializable
    data class MissingTopic(
        override val gapId: String,
        override val severity: GapSeverity,
        override val description: String,
        val topicName: String,
        val relatedExistingTopics: List<String>,
        val suggestedResources: List<String>
    ) : KnowledgeGap()

    @Serializable
    data class WeakCoverage(
        override val gapId: String,
        override val severity: GapSeverity,
        override val description: String,
        val topicId: String,
        val currentCoverage: Double,
        val targetCoverage: Double,
        val existingDocuments: List<String>
    ) : KnowledgeGap()

    @Serializable
    data class BrokenConnection(
        override val gapId: String,
        override val severity: GapSeverity,
        override val description: String,
        val sourceTopicId: String,
        val expectedTargetId: String,
        val connectionType: String
    ) : KnowledgeGap()
}

@Serializable
enum class GapSeverity {
    LOW, MEDIUM, HIGH, CRITICAL
}

@Serializable
data class GapUpdate(
    val updateType: GapUpdateType,
    val affectedGapId: String?,
    val newGap: KnowledgeGap?,
    val resolvedGapId: String?,
    val timestamp: Long
)

@Serializable
enum class GapUpdateType {
    GAP_DETECTED, GAP_RESOLVED, COVERAGE_CHANGED, DOCUMENT_ORPHANED
}

@Serializable
data class TopicCoverage(
    val topicId: String,
    val topicName: String,
    val coverageScore: Double,
    val documentCount: Int,
    val documentIds: List<String>,
    val subtopicCoverage: Map<String, Double>,
    val lastUpdated: Long
)

@Serializable
data class OrphanedDocument(
    val documentId: String,
    val documentTitle: String,
    val connectionCount: Int,
    val suggestedConnections: List<SuggestedConnection>,
    val isolationScore: Double
)

@Serializable
data class SuggestedConnection(
    val targetDocumentId: String,
    val targetTitle: String,
    val connectionType: String,
    val confidence: Double
)

@Serializable
data class TopicSuggestion(
    val topicId: String,
    val topicName: String,
    val relevanceScore: Double,
    val rationale: String,
    val relatedExistingTopics: List<String>,
    val estimatedEffort: TopicEffort
)

@Serializable
enum class TopicEffort {
    MINIMAL, MODERATE, SIGNIFICANT, EXTENSIVE
}

class AnalysisException(message: String, cause: Throwable? = null) : Exception(message, cause)
```

### Architectural Requirements

1. **Coroutines**: Use `newSuspendedTransaction` for database operations, not blocking `transaction`
2. **Flow Handling**: Implement `gapUpdatesFlow` with proper `awaitClose` for cleanup
3. **Event Integration**: Subscribe to `EventBus` for document/graph change events
4. **Caching**: Use bounded cache with stable keys (not `toString()`)
5. **Serialization**: Use `kotlinx.serialization` with explicit `@SerialName` on sealed classes
6. **Error Handling**: Rethrow `CancellationException` in `runCatching` blocks

### Acceptance Criteria

1. **Unit Tests** (minimum 25 tests):
   - Gap detection for various coverage scenarios
   - Orphan document identification with edge cases
   - Topic suggestion ranking accuracy
   - Sealed class serialization round-trip
   - Cache key stability

2. **Integration Tests** (minimum 10 tests):
   - Integration with GraphService for connection analysis
   - Integration with EmbeddingService for similarity scoring
   - Integration with DocumentService for content retrieval
   - EventBus subscription and flow updates

3. **Coverage**: Minimum 80% line coverage on `GapDetectorService.kt`

4. **Test Command**: `./gradlew :gapdetector:test`

---

## Task 2: Citation Network Analyzer

### Overview

Implement a service that analyzes citation relationships between documents, identifying influential sources, citation clusters, and potential missing citations. The analyzer builds a directed citation graph and computes bibliometric metrics.

### Module Location

```
mindvault/
  citations/
    src/main/kotlin/com/mindvault/citations/
      CitationAnalyzerService.kt
      CitationModels.kt
    src/test/kotlin/com/mindvault/citations/
      CitationAnalyzerTests.kt
    build.gradle.kts
```

### Interface Contract

```kotlin
package com.mindvault.citations

import kotlinx.coroutines.flow.Flow
import kotlinx.serialization.Serializable

/**
 * Service for analyzing citation networks within a knowledge base.
 *
 * Provides bibliometric analysis including:
 * - Citation graph construction and traversal
 * - Influence scoring (similar to PageRank)
 * - Citation cluster detection
 * - Missing citation suggestions
 * - Temporal citation pattern analysis
 */
interface CitationAnalyzer {

    /**
     * Extracts and indexes citations from a document.
     *
     * @param documentId The document to extract citations from
     * @param content The document content containing citations
     * @return Extraction result with identified citations
     */
    suspend fun extractCitations(
        documentId: String,
        content: String
    ): CitationExtractionResult

    /**
     * Computes influence score for a document based on citation network.
     *
     * Uses an iterative algorithm similar to PageRank where documents
     * cited by influential documents receive higher scores.
     *
     * @param documentId The document to score
     * @param maxIterations Maximum iterations for convergence
     * @param dampingFactor Damping factor for the algorithm (default 0.85)
     * @return Influence metrics for the document
     */
    suspend fun computeInfluenceScore(
        documentId: String,
        maxIterations: Int = 100,
        dampingFactor: Double = 0.85
    ): InfluenceMetrics

    /**
     * Identifies citation clusters - groups of documents that frequently cite each other.
     *
     * @param userId The user's knowledge base to analyze
     * @param minClusterSize Minimum documents in a cluster
     * @param similarityThreshold Minimum co-citation similarity for cluster membership
     * @return Detected clusters with their member documents
     */
    suspend fun detectCitationClusters(
        userId: String,
        minClusterSize: Int = 3,
        similarityThreshold: Double = 0.5
    ): List<CitationCluster>

    /**
     * Suggests potential citations that are missing from a document.
     *
     * Analyzes similar documents' citation patterns to identify sources
     * the document should likely reference but doesn't.
     *
     * @param documentId The document to analyze
     * @param maxSuggestions Maximum suggestions to return
     * @return Ranked list of citation suggestions with confidence scores
     */
    suspend fun suggestMissingCitations(
        documentId: String,
        maxSuggestions: Int = 10
    ): List<CitationSuggestion>

    /**
     * Builds the complete citation graph for a user's knowledge base.
     *
     * @param userId The user whose citation graph to build
     * @return The citation graph with nodes and edges
     */
    suspend fun buildCitationGraph(userId: String): CitationGraph

    /**
     * Streams citation network updates as documents are modified.
     *
     * @param userId The user to monitor
     * @return Flow of citation graph updates
     */
    fun citationUpdatesFlow(userId: String): Flow<CitationGraphUpdate>

    /**
     * Computes co-citation similarity between two documents.
     *
     * Two documents are co-citation similar if they are frequently
     * cited together by other documents.
     *
     * @param docId1 First document
     * @param docId2 Second document
     * @return Similarity score between 0.0 and 1.0
     */
    suspend fun computeCoCitationSimilarity(
        docId1: String,
        docId2: String
    ): Double

    /**
     * Analyzes citation patterns over time.
     *
     * @param documentId The document to analyze
     * @return Temporal analysis of citation accrual
     */
    suspend fun analyzeCitationTrends(
        documentId: String
    ): CitationTrendAnalysis
}
```

### Required Data Classes

```kotlin
package com.mindvault.citations

import kotlinx.serialization.Serializable
import kotlinx.serialization.SerialName

@Serializable
data class CitationExtractionResult(
    val documentId: String,
    val extractedCitations: List<ExtractedCitation>,
    val extractionConfidence: Double,
    val unrecognizedReferences: List<String>,
    val processingTimeMs: Long
)

@Serializable
data class ExtractedCitation(
    val citationId: String,
    val targetDocumentId: String?,
    val rawText: String,
    val citationType: CitationType,
    val context: String,
    val positionInDocument: Int,
    val confidence: Double
)

@Serializable
enum class CitationType {
    @SerialName("direct") DIRECT,
    @SerialName("indirect") INDIRECT,
    @SerialName("self") SELF_CITATION,
    @SerialName("external") EXTERNAL
}

@Serializable
data class InfluenceMetrics(
    val documentId: String,
    val influenceScore: Double,
    val citationCount: Int,
    val citedByCount: Int,
    val hIndex: Int,
    val selfCitationRatio: Double,
    val influentialCiters: List<String>,
    val computedAt: Long
)

@Serializable
data class CitationCluster(
    val clusterId: String,
    val clusterName: String,
    val memberDocuments: List<String>,
    val coreDocuments: List<String>,
    val cohesionScore: Double,
    val dominantTopics: List<String>,
    val internalCitationDensity: Double
)

@Serializable
data class CitationSuggestion(
    val suggestedDocumentId: String,
    val suggestedTitle: String,
    val confidence: Double,
    val rationale: CitationRationale,
    val citingDocuments: List<String>,
    val relevantSections: List<String>
)

@Serializable
sealed class CitationRationale {
    @Serializable
    @SerialName("co_citation")
    data class CoCitation(
        val sharedCiters: Int,
        val similarDocuments: List<String>
    ) : CitationRationale()

    @Serializable
    @SerialName("topic_coverage")
    data class TopicCoverage(
        val topic: String,
        val coverageGap: Double
    ) : CitationRationale()

    @Serializable
    @SerialName("authoritative_source")
    data class AuthoritativeSource(
        val authorityScore: Double,
        val domain: String
    ) : CitationRationale()
}

@Serializable
data class CitationGraph(
    val userId: String,
    val nodes: List<CitationNode>,
    val edges: List<CitationEdge>,
    val statistics: GraphStatistics,
    val buildTimestamp: Long
)

@Serializable
data class CitationNode(
    val documentId: String,
    val title: String,
    val citationCount: Int,
    val citedByCount: Int,
    val influenceScore: Double
)

@Serializable
data class CitationEdge(
    val sourceId: String,
    val targetId: String,
    val citationType: CitationType,
    val weight: Double,
    val context: String?
)

@Serializable
data class GraphStatistics(
    val totalNodes: Int,
    val totalEdges: Int,
    val averageCitationsPerDocument: Double,
    val networkDensity: Double,
    val largestComponentSize: Int,
    val isolatedNodeCount: Int
)

@Serializable
data class CitationGraphUpdate(
    val updateType: CitationUpdateType,
    val affectedDocumentIds: List<String>,
    val addedEdges: List<CitationEdge>,
    val removedEdges: List<CitationEdge>,
    val timestamp: Long
)

@Serializable
enum class CitationUpdateType {
    CITATION_ADDED, CITATION_REMOVED, DOCUMENT_ADDED, DOCUMENT_REMOVED, BULK_UPDATE
}

@Serializable
data class CitationTrendAnalysis(
    val documentId: String,
    val totalCitations: Int,
    val citationsOverTime: List<TimePeriodCitations>,
    val peakCitationPeriod: String?,
    val citationVelocity: Double,
    val trend: CitationTrend
)

@Serializable
data class TimePeriodCitations(
    val period: String,
    val citationCount: Int,
    val cumulativeCount: Int
)

@Serializable
enum class CitationTrend {
    RISING, STABLE, DECLINING, DORMANT
}
```

### Architectural Requirements

1. **Graph Integration**: Integrate with `GraphService` for storing citation relationships
2. **Mutex Usage**: Use `ReadWriteMutex` pattern (not single `Mutex`) for concurrent graph access
3. **Value Classes**: Avoid using value classes as `HashMap` keys directly
4. **Null Safety**: Handle platform types from JDBC with explicit null checks
5. **Serialization**: Use distinct `@SerialName` for sealed class discriminators
6. **Structured Concurrency**: Use `coroutineScope` for parallel computations

### Acceptance Criteria

1. **Unit Tests** (minimum 30 tests):
   - Citation extraction from various formats
   - Influence score computation convergence
   - Cluster detection accuracy
   - Graph traversal correctness
   - Sealed class serialization with distinct discriminators

2. **Integration Tests** (minimum 15 tests):
   - Integration with GraphService for edge storage
   - Integration with SearchService for document retrieval
   - EventBus integration for real-time updates
   - Database transaction handling

3. **Performance Tests** (minimum 5 tests):
   - Influence score computation on 1000+ node graph
   - Cluster detection scalability
   - Cache effectiveness under load

4. **Coverage**: Minimum 80% line coverage on `CitationAnalyzerService.kt`

5. **Test Command**: `./gradlew :citations:test`

---

## Task 3: Auto-Tagging Service

### Overview

Implement an intelligent auto-tagging service that automatically assigns tags to documents based on content analysis, existing tag patterns, and semantic similarity. The service learns from user tagging behavior to improve suggestions over time.

### Module Location

```
mindvault/
  autotag/
    src/main/kotlin/com/mindvault/autotag/
      AutoTagService.kt
      AutoTagModels.kt
      TagLearningModel.kt
    src/test/kotlin/com/mindvault/autotag/
      AutoTagTests.kt
    build.gradle.kts
```

### Interface Contract

```kotlin
package com.mindvault.autotag

import kotlinx.coroutines.flow.Flow
import kotlinx.serialization.Serializable

/**
 * Service for automatic document tagging based on content analysis.
 *
 * Provides intelligent tagging through:
 * - Content-based tag extraction
 * - Learning from user tagging patterns
 * - Semantic similarity with existing tagged documents
 * - Tag hierarchy and relationship management
 * - Batch tagging operations
 */
interface AutoTagService {

    /**
     * Generates tag suggestions for a document based on its content.
     *
     * @param documentId The document to analyze
     * @param content The document content (if not already indexed)
     * @param options Configuration for tag generation
     * @return Ranked list of tag suggestions with confidence scores
     */
    suspend fun suggestTags(
        documentId: String,
        content: String? = null,
        options: TagSuggestionOptions = TagSuggestionOptions()
    ): TagSuggestionResult

    /**
     * Automatically applies tags to a document based on high-confidence suggestions.
     *
     * Only applies tags above the confidence threshold. Returns the applied
     * tags and any suggestions that were below threshold.
     *
     * @param documentId The document to tag
     * @param confidenceThreshold Minimum confidence for auto-application (default 0.8)
     * @return Result containing applied and suggested tags
     */
    suspend fun autoApplyTags(
        documentId: String,
        confidenceThreshold: Double = 0.8
    ): AutoTagResult

    /**
     * Records user feedback on tag suggestions to improve the model.
     *
     * @param documentId The document that was tagged
     * @param acceptedTags Tags the user accepted/added
     * @param rejectedTags Tags the user explicitly rejected
     * @param addedTags New tags the user added that weren't suggested
     */
    suspend fun recordTagFeedback(
        documentId: String,
        acceptedTags: List<String>,
        rejectedTags: List<String>,
        addedTags: List<String>
    )

    /**
     * Processes tags for multiple documents in batch.
     *
     * @param documentIds Documents to process
     * @param applyAutomatically Whether to auto-apply high-confidence tags
     * @param progressCallback Called with progress updates
     * @return Batch processing results
     */
    suspend fun batchProcessTags(
        documentIds: List<String>,
        applyAutomatically: Boolean = false,
        progressCallback: (BatchProgress) -> Unit = {}
    ): BatchTagResult

    /**
     * Retrieves the tag hierarchy with usage statistics.
     *
     * @param userId The user whose tag hierarchy to retrieve
     * @return Tag hierarchy tree with statistics
     */
    suspend fun getTagHierarchy(userId: String): TagHierarchy

    /**
     * Finds documents similar to those with a specific tag.
     *
     * @param tagName The tag to find similar documents for
     * @param userId The user's document collection
     * @param limit Maximum documents to return
     * @return Documents that might deserve the tag but don't have it
     */
    suspend fun findCandidatesForTag(
        tagName: String,
        userId: String,
        limit: Int = 20
    ): List<TagCandidate>

    /**
     * Merges duplicate or similar tags across documents.
     *
     * @param userId The user whose tags to analyze
     * @param similarityThreshold Minimum similarity for merge suggestion
     * @return Suggested tag merges
     */
    suspend fun suggestTagMerges(
        userId: String,
        similarityThreshold: Double = 0.85
    ): List<TagMergeSuggestion>

    /**
     * Streams tag suggestions as documents are modified.
     *
     * @param userId The user to monitor
     * @return Flow of tag suggestion updates
     */
    fun tagSuggestionsFlow(userId: String): Flow<TagSuggestionUpdate>

    /**
     * Computes tag co-occurrence statistics.
     *
     * @param userId The user's document collection
     * @return Matrix of tag co-occurrence frequencies
     */
    suspend fun computeTagCoOccurrence(userId: String): TagCoOccurrenceMatrix
}
```

### Required Data Classes

```kotlin
package com.mindvault.autotag

import kotlinx.serialization.Serializable
import kotlinx.serialization.SerialName

@Serializable
data class TagSuggestionOptions(
    val maxSuggestions: Int = 10,
    val minConfidence: Double = 0.3,
    val includeHierarchicalTags: Boolean = true,
    val useSemanticSimilarity: Boolean = true,
    val useContentExtraction: Boolean = true,
    val useUserPatterns: Boolean = true
)

@Serializable
data class TagSuggestionResult(
    val documentId: String,
    val suggestions: List<TagSuggestion>,
    val existingTags: List<String>,
    val processingTimeMs: Long,
    val modelVersion: String
)

@Serializable
data class TagSuggestion(
    val tagName: String,
    val confidence: Double,
    val source: TagSource,
    val reasoning: String,
    val parentTag: String?,
    val relatedTags: List<String>
)

@Serializable
sealed class TagSource {
    @Serializable
    @SerialName("content_extraction")
    data class ContentExtraction(
        val matchedTerms: List<String>,
        val termFrequency: Int
    ) : TagSource()

    @Serializable
    @SerialName("semantic_similarity")
    data class SemanticSimilarity(
        val similarDocumentId: String,
        val similarityScore: Double
    ) : TagSource()

    @Serializable
    @SerialName("user_pattern")
    data class UserPattern(
        val patternType: String,
        val occurrenceCount: Int
    ) : TagSource()

    @Serializable
    @SerialName("hierarchy_inference")
    data class HierarchyInference(
        val parentTag: String,
        val inferenceConfidence: Double
    ) : TagSource()
}

@Serializable
data class AutoTagResult(
    val documentId: String,
    val appliedTags: List<AppliedTag>,
    val suggestedTags: List<TagSuggestion>,
    val skippedTags: List<SkippedTag>
)

@Serializable
data class AppliedTag(
    val tagName: String,
    val confidence: Double,
    val source: TagSource,
    val appliedAt: Long
)

@Serializable
data class SkippedTag(
    val tagName: String,
    val confidence: Double,
    val reason: SkipReason
)

@Serializable
enum class SkipReason {
    BELOW_THRESHOLD, ALREADY_EXISTS, USER_REJECTED, CONFLICTING_TAG
}

@Serializable
data class BatchProgress(
    val processedCount: Int,
    val totalCount: Int,
    val currentDocumentId: String,
    val successCount: Int,
    val errorCount: Int
)

@Serializable
data class BatchTagResult(
    val processedDocuments: Int,
    val appliedTagsCount: Int,
    val suggestedTagsCount: Int,
    val errors: List<BatchError>,
    val processingTimeMs: Long
)

@Serializable
data class BatchError(
    val documentId: String,
    val errorMessage: String,
    val errorType: String
)

@Serializable
data class TagHierarchy(
    val userId: String,
    val rootTags: List<TagNode>,
    val totalTags: Int,
    val maxDepth: Int,
    val lastUpdated: Long
)

@Serializable
data class TagNode(
    val tagName: String,
    val documentCount: Int,
    val children: List<TagNode>,
    val depth: Int,
    val path: List<String>
)

@Serializable
data class TagCandidate(
    val documentId: String,
    val documentTitle: String,
    val matchScore: Double,
    val matchingFeatures: List<String>,
    val currentTags: List<String>
)

@Serializable
data class TagMergeSuggestion(
    val primaryTag: String,
    val duplicateTags: List<String>,
    val similarity: Double,
    val documentOverlap: Int,
    val suggestedMergedName: String?
)

@Serializable
data class TagSuggestionUpdate(
    val documentId: String,
    val updateType: TagUpdateType,
    val newSuggestions: List<TagSuggestion>,
    val removedSuggestions: List<String>,
    val timestamp: Long
)

@Serializable
enum class TagUpdateType {
    DOCUMENT_MODIFIED, MODEL_UPDATED, FEEDBACK_APPLIED, TAG_HIERARCHY_CHANGED
}

@Serializable
data class TagCoOccurrenceMatrix(
    val tags: List<String>,
    val coOccurrences: List<List<Int>>,
    val documentCounts: Map<String, Int>,
    val computedAt: Long
)
```

### Architectural Requirements

1. **Learning Model**: Implement a simple learning model that improves based on feedback
2. **Embedding Integration**: Use `EmbeddingService` for semantic similarity calculations
3. **DSL Builder**: Implement tag query DSL with proper `@DslMarker` annotation
4. **Data Class Equality**: Handle `ByteArray` in data classes with custom `equals`/`hashCode` if needed
5. **Copy Safety**: Ensure `copy()` on data classes with mutable collections performs deep copy
6. **Cache Stampede Prevention**: Use single-flight pattern for expensive tag computations
7. **MDC Propagation**: Use `MDCContext()` when switching coroutine dispatchers

### Acceptance Criteria

1. **Unit Tests** (minimum 35 tests):
   - Tag suggestion accuracy for various content types
   - Feedback recording and model updates
   - Batch processing with cancellation support
   - Tag hierarchy traversal
   - Sealed class serialization with distinct discriminators
   - Data class copy behavior with mutable fields

2. **Integration Tests** (minimum 15 tests):
   - Integration with EmbeddingService for semantic similarity
   - Integration with DocumentService for content retrieval
   - Integration with SearchService for tag search
   - EventBus subscription for document change events
   - Database transaction handling across services

3. **Learning Tests** (minimum 5 tests):
   - Model improvement after feedback
   - Feedback-based ranking adjustments
   - Pattern recognition from user behavior

4. **Performance Tests** (minimum 5 tests):
   - Batch processing of 100+ documents
   - Tag suggestion latency
   - Cache stampede prevention under concurrent load

5. **Coverage**: Minimum 80% line coverage on `AutoTagService.kt` and `TagLearningModel.kt`

6. **Test Command**: `./gradlew :autotag:test`

---

## General Requirements for All Tasks

### Build Configuration

Each new module must have a `build.gradle.kts` with:

```kotlin
plugins {
    kotlin("jvm")
    kotlin("plugin.serialization")
}

dependencies {
    implementation(project(":shared"))
    implementation("io.ktor:ktor-server-core:2.3.7")
    implementation("org.jetbrains.exposed:exposed-core:0.45.0")
    implementation("org.jetbrains.exposed:exposed-dao:0.45.0")
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-core:1.7.3")
    implementation("org.jetbrains.kotlinx:kotlinx-serialization-json:1.6.2")

    testImplementation("org.jetbrains.kotlin:kotlin-test-junit5")
    testImplementation("org.jetbrains.kotlinx:kotlinx-coroutines-test:1.7.3")
    testImplementation("io.mockk:mockk:1.13.8")
}
```

### Common Patterns to Follow

1. **Suspend Functions**: All database and network operations must be `suspend` functions
2. **Structured Concurrency**: Use `coroutineScope` for parallel work, not `GlobalScope`
3. **Transaction Handling**: Use `newSuspendedTransaction` with appropriate dispatchers
4. **Error Handling**: Always rethrow `CancellationException` in error handlers
5. **Logging**: Use `MDCContext()` when crossing coroutine boundaries
6. **Caching**: Use bounded caches with stable keys
7. **Serialization**: Register all sealed class subclasses with unique discriminators

### Testing Patterns

Follow existing test patterns from `SearchTests.kt` and `GraphTests.kt`:
- Test both happy path and error cases
- Test concurrent access scenarios
- Test serialization round-trips
- Use `runTest` for coroutine tests
- Include local stub classes that simulate buggy behavior for bug-specific tests

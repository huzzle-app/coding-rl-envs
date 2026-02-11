# MindVault - Greenfield Tasks

## Overview

These 3 greenfield tasks require implementing NEW modules from scratch within the MindVault platform. Each task builds upon existing infrastructure (EventBus, models, services) and must follow established architectural patterns for coroutines, serialization, database access, and testing.

## Environment

- **Language**: Kotlin 1.9 | Ktor 2.3 | Exposed ORM
- **Infrastructure**: PostgreSQL 16, Redis 7, Kafka 3.6, Consul 1.17
- **Difficulty**: Principal (8-16 hours)

## Tasks

### Task 1: Knowledge Gap Detector (Greenfield Service)

Implement a service that analyzes a user's knowledge base to identify gaps, missing connections, and potential areas for expansion. The detector compares document coverage against a reference ontology and suggests topics for exploration.

**Interface Contract**: Implement `KnowledgeGapDetector` with methods for:
- `analyzeKnowledgeGaps()` - Main analysis returning identified gaps and recommendations
- `gapUpdatesFlow()` - Stream incremental updates as documents are modified
- `computeTopicCoverage()` - Coverage metrics for specific topics
- `findOrphanedDocuments()` - Identify isolated documents with suggestions
- `suggestTopics()` - Ranked topic recommendations based on patterns

**Data Classes**: Sealed class hierarchy for `KnowledgeGap` (MissingTopic, WeakCoverage, BrokenConnection), `GapAnalysisResult`, `TopicCoverage`, `OrphanedDocument`, `TopicSuggestion` with `TopicEffort` enum.

**Module Location**:
```
mindvault/gapdetector/
├── src/main/kotlin/com/mindvault/gapdetector/
│   ├── GapDetectorService.kt
│   └── GapDetectorModels.kt
├── src/test/kotlin/com/mindvault/gapdetector/
│   └── GapDetectorTests.kt
└── build.gradle.kts
```

### Task 2: Citation Network Analyzer (Greenfield Service)

Implement a service that analyzes citation relationships between documents, identifying influential sources, citation clusters, and potential missing citations. The analyzer builds a directed citation graph and computes bibliometric metrics.

**Interface Contract**: Implement `CitationAnalyzer` with methods for:
- `extractCitations()` - Extract citations from document content
- `computeInfluenceScore()` - PageRank-like scoring for documents
- `detectCitationClusters()` - Identify groups of frequently co-citing documents
- `suggestMissingCitations()` - Recommend citations based on similar documents
- `buildCitationGraph()` - Complete directed citation graph
- `citationUpdatesFlow()` - Stream citation network updates
- `computeCoCitationSimilarity()` - Co-citation similarity between documents
- `analyzeCitationTrends()` - Temporal citation pattern analysis

**Data Classes**: `CitationExtractionResult`, `ExtractedCitation`, sealed `CitationType`, `InfluenceMetrics`, `CitationCluster`, sealed `CitationRationale` (CoCitation, TopicCoverage, AuthoritativeSource), `CitationGraph` with nodes/edges, `CitationTrendAnalysis`.

**Module Location**:
```
mindvault/citations/
├── src/main/kotlin/com/mindvault/citations/
│   ├── CitationAnalyzerService.kt
│   └── CitationModels.kt
├── src/test/kotlin/com/mindvault/citations/
│   └── CitationAnalyzerTests.kt
└── build.gradle.kts
```

### Task 3: Auto-Tagging Service (Greenfield Service)

Implement an intelligent auto-tagging service that automatically assigns tags to documents based on content analysis, existing tag patterns, and semantic similarity. The service learns from user tagging behavior to improve suggestions over time.

**Interface Contract**: Implement `AutoTagService` with methods for:
- `suggestTags()` - Generate tag suggestions with confidence scores
- `autoApplyTags()` - Automatically apply high-confidence tags
- `recordTagFeedback()` - Learn from user feedback
- `batchProcessTags()` - Process multiple documents with progress callback
- `getTagHierarchy()` - Retrieve tag hierarchy with statistics
- `findCandidatesForTag()` - Find documents that might deserve a tag
- `suggestTagMerges()` - Merge duplicate/similar tags
- `tagSuggestionsFlow()` - Stream tag suggestion updates
- `computeTagCoOccurrence()` - Tag co-occurrence statistics

**Data Classes**: `TagSuggestionOptions`, `TagSuggestionResult`, sealed `TagSource` (ContentExtraction, SemanticSimilarity, UserPattern, HierarchyInference), `AutoTagResult`, `AppliedTag`, `SkippedTag`, sealed `SkipReason`, `TagHierarchy` with `TagNode`, `TagCandidate`, `TagMergeSuggestion`, `TagCoOccurrenceMatrix`.

**Module Location**:
```
mindvault/autotag/
├── src/main/kotlin/com/mindvault/autotag/
│   ├── AutoTagService.kt
│   ├── AutoTagModels.kt
│   └── TagLearningModel.kt
├── src/test/kotlin/com/mindvault/autotag/
│   └── AutoTagTests.kt
└── build.gradle.kts
```

## Getting Started

### Prerequisites

Before starting any greenfield task:
1. Ensure the existing test suite passes: `./gradlew test`
2. Review existing service patterns in `documents/`, `search/`, `graph/`, `embeddings/`
3. Understand the shared infrastructure in `shared/` (EventBus, models, serialization)

### Development

```bash
cd /Users/amit/projects/terminal-bench-envs/kotlin/mindvault

# Start infrastructure
docker compose up -d

# Develop and test your new module
./gradlew :gapdetector:test
./gradlew :citations:test
./gradlew :autotag:test
```

## Architectural Requirements

- **Coroutines**: Use `newSuspendedTransaction` for database operations, structured concurrency with `coroutineScope`
- **Flow Handling**: Implement flows with proper `awaitClose` for cleanup
- **Event Integration**: Subscribe to `EventBus` for service change events
- **Caching**: Use bounded caches with stable keys (not `toString()`)
- **Serialization**: Use `kotlinx.serialization` with explicit `@SerialName` on sealed classes
- **Error Handling**: Rethrow `CancellationException` in `runCatching` blocks
- **DSL Builders**: Use `@DslMarker` for safe DSL construction
- **Thread Safety**: Use appropriate locking (Mutex, ReadWriteMutex) for concurrent access

## Success Criteria

Each task requires:

1. **Unit Tests** (25-35 tests minimum):
   - Happy path and error cases
   - Sealed class serialization round-trips
   - Cache behavior and key stability
   - Concurrent access scenarios

2. **Integration Tests** (10-15 tests minimum):
   - Integration with existing services
   - EventBus subscription and updates
   - Database transaction handling
   - Performance characteristics

3. **Coverage**: Minimum 80% line coverage on main service implementation

4. **Test Command**: `./gradlew :<module>:test`

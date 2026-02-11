# MediaFlow - Greenfield Implementation Tasks

This document defines new modules to be implemented from scratch for the MediaFlow video streaming platform. Each task requires creating a complete service following existing architectural patterns.

## Prerequisites

Before starting any task:
1. Review existing service patterns in `services/` directory
2. Understand the shared module structure in `shared/`
3. Familiarize yourself with the Express + Jest test patterns
4. Run `npm install` and `npm test` to verify environment setup

---

## Task 1: Content Recommendation Engine

### Overview

Implement a machine learning-inspired content recommendation engine that provides personalized video suggestions based on user behavior, content similarity, and trending signals.

### Service Location

```
services/content-recommender/
  src/
    index.js           # Express app entry point
    services/
      engine.js        # Core recommendation engine
      similarity.js    # Content similarity calculator
      trending.js      # Trending content tracker
    repositories/
      interaction.js   # User interaction repository
```

### Interface Contract

```javascript
/**
 * ContentRecommendationEngine
 *
 * Provides personalized video recommendations using collaborative filtering
 * and content-based similarity algorithms.
 */
class ContentRecommendationEngine {
  /**
   * @param {Object} options - Configuration options
   * @param {Object} options.db - Database connection
   * @param {Object} options.cache - Redis cache client
   * @param {Object} options.eventBus - Event bus for async updates
   */
  constructor(options) {}

  /**
   * Get personalized recommendations for a user
   *
   * @param {string} userId - Target user ID
   * @param {Object} options - Recommendation options
   * @param {number} options.limit - Max recommendations (default: 20)
   * @param {string[]} options.excludeVideoIds - Videos to exclude
   * @param {string} options.context - Viewing context ('home', 'watch_next', 'search')
   * @returns {Promise<Recommendation[]>} Ranked recommendations
   */
  async getRecommendations(userId, options = {}) {}

  /**
   * Record user interaction for model updates
   *
   * @param {string} userId - User ID
   * @param {string} videoId - Video ID
   * @param {InteractionType} type - Type of interaction
   * @param {Object} metadata - Additional context
   * @returns {Promise<void>}
   */
  async recordInteraction(userId, videoId, type, metadata = {}) {}

  /**
   * Compute similarity score between two videos
   *
   * @param {string} videoIdA - First video ID
   * @param {string} videoIdB - Second video ID
   * @returns {Promise<number>} Similarity score 0.0-1.0
   */
  async computeSimilarity(videoIdA, videoIdB) {}

  /**
   * Rebuild user preference model
   *
   * @param {string} userId - User ID to rebuild
   * @returns {Promise<UserPreferenceModel>}
   */
  async rebuildUserModel(userId) {}

  /**
   * Get trending videos with time decay
   *
   * @param {Object} options - Trending options
   * @param {number} options.windowHours - Time window (default: 24)
   * @param {string} options.category - Optional category filter
   * @returns {Promise<TrendingVideo[]>}
   */
  async getTrending(options = {}) {}
}

/**
 * SimilarityCalculator
 *
 * Computes content-based and collaborative similarity scores.
 */
class SimilarityCalculator {
  /**
   * Calculate content-based similarity using video metadata
   *
   * @param {VideoMetadata} videoA - First video metadata
   * @param {VideoMetadata} videoB - Second video metadata
   * @returns {number} Similarity score 0.0-1.0
   */
  calculateContentSimilarity(videoA, videoB) {}

  /**
   * Calculate collaborative similarity based on user co-viewing
   *
   * @param {string} videoIdA - First video ID
   * @param {string} videoIdB - Second video ID
   * @param {Map<string, Set<string>>} userViewHistory - User viewing data
   * @returns {number} Jaccard similarity coefficient
   */
  calculateCollaborativeSimilarity(videoIdA, videoIdB, userViewHistory) {}

  /**
   * Build similarity matrix for a set of videos
   *
   * @param {string[]} videoIds - Videos to compute similarities for
   * @returns {Promise<Map<string, Map<string, number>>>} Similarity matrix
   */
  async buildSimilarityMatrix(videoIds) {}
}

/**
 * TrendingTracker
 *
 * Tracks and scores trending content with time decay.
 */
class TrendingTracker {
  /**
   * @param {Object} options - Configuration
   * @param {number} options.decayHalfLife - Half-life in hours (default: 6)
   */
  constructor(options = {}) {}

  /**
   * Record engagement signal for trending calculation
   *
   * @param {string} videoId - Video ID
   * @param {EngagementType} type - Type of engagement
   * @param {number} weight - Signal weight
   * @returns {Promise<void>}
   */
  async recordEngagement(videoId, type, weight = 1) {}

  /**
   * Get current trending score for a video
   *
   * @param {string} videoId - Video ID
   * @returns {Promise<number>} Trending score
   */
  async getTrendingScore(videoId) {}

  /**
   * Get top trending videos
   *
   * @param {number} limit - Max results
   * @param {string} category - Optional category filter
   * @returns {Promise<TrendingVideo[]>}
   */
  async getTopTrending(limit = 50, category = null) {}
}
```

### Data Structures

```javascript
/**
 * @typedef {Object} Recommendation
 * @property {string} videoId - Recommended video ID
 * @property {number} score - Relevance score 0.0-1.0
 * @property {string} reason - Why this was recommended
 * @property {string[]} signals - Contributing signals
 */

/**
 * @typedef {'view' | 'like' | 'share' | 'complete' | 'skip' | 'save'} InteractionType
 */

/**
 * @typedef {Object} UserPreferenceModel
 * @property {string} userId
 * @property {Map<string, number>} categoryWeights
 * @property {Map<string, number>} tagWeights
 * @property {string[]} recentVideoIds
 * @property {Date} lastUpdated
 */

/**
 * @typedef {Object} VideoMetadata
 * @property {string} id
 * @property {string} title
 * @property {string[]} tags
 * @property {string} category
 * @property {number} duration
 * @property {string} creatorId
 */

/**
 * @typedef {Object} TrendingVideo
 * @property {string} videoId
 * @property {number} trendingScore
 * @property {number} velocity - Rate of score change
 * @property {number} views24h
 * @property {Date} publishedAt
 */

/**
 * @typedef {'view' | 'like' | 'comment' | 'share'} EngagementType
 */
```

### Architectural Requirements

1. **Follow existing patterns**: Use Express app structure from `services/recommendations/src/index.js`
2. **Event integration**: Consume events from `EventBus` for real-time updates
3. **Caching strategy**: Use Redis for similarity matrix and trending scores (avoid hot-key issues)
4. **Database**: Use PostgreSQL for persistent interaction storage
5. **Port**: 3010 (next available after analytics on 3009)

### Acceptance Criteria

1. **Unit tests** (minimum 25 tests in `tests/unit/content-recommender/`):
   - Similarity calculation accuracy
   - Trending score decay correctness
   - User model building
   - Edge cases (empty history, new users, cold start)

2. **Integration tests** (minimum 10 tests in `tests/integration/content-recommender.test.js`):
   - End-to-end recommendation flow
   - Event consumption and model updates
   - Cache invalidation

3. **Performance tests**:
   - Similarity matrix computation < 100ms for 1000 videos
   - Recommendation latency < 50ms (cached)

4. **Test command**: `npm test -- --testPathPattern=content-recommender`

---

## Task 2: Video Clip Generator Service

### Overview

Implement a service that generates short video clips from full-length videos, supporting automatic highlight detection, custom time ranges, and social media format exports.

### Service Location

```
services/clip-generator/
  src/
    index.js           # Express app entry point
    services/
      generator.js     # Core clip generation logic
      highlights.js    # Automatic highlight detection
      exporter.js      # Format-specific export handlers
    workers/
      processor.js     # Background job processor
```

### Interface Contract

```javascript
/**
 * ClipGeneratorService
 *
 * Generates video clips from source videos with various export formats.
 */
class ClipGeneratorService {
  /**
   * @param {Object} options - Configuration
   * @param {Object} options.storage - MinIO/S3 storage client
   * @param {Object} options.queue - RabbitMQ job queue
   * @param {Object} options.transcoder - Transcode service client
   */
  constructor(options) {}

  /**
   * Create a clip from a source video
   *
   * @param {ClipRequest} request - Clip generation request
   * @returns {Promise<ClipJob>} Job tracking object
   */
  async createClip(request) {}

  /**
   * Get status of a clip generation job
   *
   * @param {string} jobId - Job ID
   * @returns {Promise<ClipJob>}
   */
  async getJobStatus(jobId) {}

  /**
   * Cancel a pending clip job
   *
   * @param {string} jobId - Job ID
   * @returns {Promise<boolean>} True if cancelled
   */
  async cancelJob(jobId) {}

  /**
   * Detect highlight moments in a video
   *
   * @param {string} videoId - Source video ID
   * @param {HighlightOptions} options - Detection options
   * @returns {Promise<HighlightSegment[]>}
   */
  async detectHighlights(videoId, options = {}) {}

  /**
   * Export clip to social media format
   *
   * @param {string} clipId - Generated clip ID
   * @param {ExportFormat} format - Target format
   * @returns {Promise<ExportResult>}
   */
  async exportToFormat(clipId, format) {}

  /**
   * Get available export formats
   *
   * @returns {ExportFormatSpec[]}
   */
  getAvailableFormats() {}
}

/**
 * HighlightDetector
 *
 * Analyzes videos to find highlight-worthy segments.
 */
class HighlightDetector {
  /**
   * Analyze audio peaks for highlight detection
   *
   * @param {string} videoId - Video ID
   * @returns {Promise<AudioPeak[]>} Detected audio peaks
   */
  async analyzeAudioPeaks(videoId) {}

  /**
   * Detect scene changes
   *
   * @param {string} videoId - Video ID
   * @param {number} threshold - Change threshold 0.0-1.0
   * @returns {Promise<SceneChange[]>}
   */
  async detectSceneChanges(videoId, threshold = 0.3) {}

  /**
   * Score segments by engagement potential
   *
   * @param {string} videoId - Video ID
   * @param {SegmentData[]} segments - Candidate segments
   * @returns {Promise<ScoredSegment[]>}
   */
  async scoreSegments(videoId, segments) {}

  /**
   * Generate automatic highlights
   *
   * @param {string} videoId - Video ID
   * @param {number} targetDuration - Target total highlight duration
   * @param {number} maxClips - Maximum number of clips
   * @returns {Promise<HighlightSegment[]>}
   */
  async generateAutoHighlights(videoId, targetDuration, maxClips) {}
}

/**
 * ClipExporter
 *
 * Handles format-specific clip exports.
 */
class ClipExporter {
  /**
   * Export for Instagram Reels (9:16, max 90s)
   *
   * @param {string} clipPath - Source clip path
   * @param {CropOptions} cropOptions - Crop/pan settings
   * @returns {Promise<string>} Exported file path
   */
  async exportInstagramReel(clipPath, cropOptions) {}

  /**
   * Export for TikTok (9:16, max 3min)
   *
   * @param {string} clipPath - Source clip path
   * @param {CropOptions} cropOptions - Crop/pan settings
   * @returns {Promise<string>} Exported file path
   */
  async exportTikTok(clipPath, cropOptions) {}

  /**
   * Export for YouTube Shorts (9:16, max 60s)
   *
   * @param {string} clipPath - Source clip path
   * @param {CropOptions} cropOptions - Crop/pan settings
   * @returns {Promise<string>} Exported file path
   */
  async exportYouTubeShort(clipPath, cropOptions) {}

  /**
   * Export for Twitter/X (16:9 or 1:1, max 2:20)
   *
   * @param {string} clipPath - Source clip path
   * @param {AspectRatio} aspectRatio - Target aspect ratio
   * @returns {Promise<string>} Exported file path
   */
  async exportTwitter(clipPath, aspectRatio) {}

  /**
   * Generate thumbnail for clip
   *
   * @param {string} clipPath - Source clip path
   * @param {number} timestamp - Thumbnail timestamp in seconds
   * @returns {Promise<string>} Thumbnail path
   */
  async generateThumbnail(clipPath, timestamp) {}
}
```

### Data Structures

```javascript
/**
 * @typedef {Object} ClipRequest
 * @property {string} videoId - Source video ID
 * @property {number} startTime - Start time in seconds
 * @property {number} endTime - End time in seconds
 * @property {string} title - Clip title
 * @property {ClipSettings} settings - Processing settings
 */

/**
 * @typedef {Object} ClipSettings
 * @property {string} quality - Output quality ('low', 'medium', 'high', 'source')
 * @property {boolean} includeAudio - Include audio track
 * @property {FadeSettings} fade - Fade in/out settings
 * @property {WatermarkSettings} watermark - Optional watermark
 */

/**
 * @typedef {Object} ClipJob
 * @property {string} id - Job ID
 * @property {string} videoId - Source video ID
 * @property {JobStatus} status - Current status
 * @property {number} progress - Progress 0-100
 * @property {string} outputUrl - Result URL (when complete)
 * @property {string} error - Error message (if failed)
 * @property {Date} createdAt
 * @property {Date} updatedAt
 */

/**
 * @typedef {'pending' | 'processing' | 'completed' | 'failed' | 'cancelled'} JobStatus
 */

/**
 * @typedef {Object} HighlightSegment
 * @property {number} startTime - Start time in seconds
 * @property {number} endTime - End time in seconds
 * @property {number} score - Highlight score 0.0-1.0
 * @property {string} type - Highlight type ('peak', 'scene_change', 'engagement')
 * @property {Object} metadata - Additional detection metadata
 */

/**
 * @typedef {Object} HighlightOptions
 * @property {number} minDuration - Minimum segment duration (default: 5)
 * @property {number} maxDuration - Maximum segment duration (default: 60)
 * @property {number} minScore - Minimum highlight score (default: 0.5)
 * @property {string[]} types - Types to detect
 */

/**
 * @typedef {'instagram_reel' | 'tiktok' | 'youtube_short' | 'twitter' | 'facebook'} ExportFormat
 */

/**
 * @typedef {Object} ExportFormatSpec
 * @property {ExportFormat} format
 * @property {string} aspectRatio
 * @property {number} maxDuration - Max duration in seconds
 * @property {number} maxFileSize - Max file size in bytes
 * @property {string[]} supportedCodecs
 */

/**
 * @typedef {Object} ExportResult
 * @property {string} clipId
 * @property {ExportFormat} format
 * @property {string} url - Download URL
 * @property {number} fileSize
 * @property {Object} metadata
 */

/**
 * @typedef {Object} CropOptions
 * @property {'center' | 'left' | 'right' | 'auto'} horizontalAlign
 * @property {'center' | 'top' | 'bottom' | 'auto'} verticalAlign
 * @property {boolean} smartCrop - Use face/object detection for cropping
 */

/**
 * @typedef {'16:9' | '9:16' | '1:1' | '4:5'} AspectRatio
 */
```

### Architectural Requirements

1. **Async processing**: Use RabbitMQ for job queue (follow `services/transcode/` pattern)
2. **Storage**: Use MinIO for source videos and generated clips
3. **Integration**: Call transcode service for actual video processing
4. **Event publishing**: Emit `clip.created`, `clip.completed`, `clip.failed` events
5. **Port**: 3011

### Acceptance Criteria

1. **Unit tests** (minimum 30 tests in `tests/unit/clip-generator/`):
   - Clip request validation
   - Highlight detection algorithms
   - Format export specifications
   - Job state machine transitions

2. **Integration tests** (minimum 15 tests in `tests/integration/clip-generator.test.js`):
   - End-to-end clip creation flow
   - Job queue processing
   - Storage integration
   - Event emission

3. **Contract tests** (minimum 5 tests):
   - API contract with transcode service
   - Storage API contract

4. **Test command**: `npm test -- --testPathPattern=clip-generator`

---

## Task 3: Content Moderation Queue

### Overview

Implement a content moderation system that queues uploaded videos for review, supports automated pre-screening, human review workflows, and enforcement actions.

### Service Location

```
services/moderation/
  src/
    index.js           # Express app entry point
    services/
      queue.js         # Moderation queue manager
      prescreener.js   # Automated pre-screening
      reviewer.js      # Human review workflow
      enforcer.js      # Enforcement action handler
    repositories/
      case.js          # Moderation case repository
```

### Interface Contract

```javascript
/**
 * ModerationQueueManager
 *
 * Manages the content moderation workflow queue.
 */
class ModerationQueueManager {
  /**
   * @param {Object} options - Configuration
   * @param {Object} options.db - Database connection
   * @param {Object} options.eventBus - Event bus
   * @param {Object} options.catalogClient - Catalog service client
   */
  constructor(options) {}

  /**
   * Submit content for moderation
   *
   * @param {ModerationSubmission} submission - Content submission
   * @returns {Promise<ModerationCase>} Created case
   */
  async submitForReview(submission) {}

  /**
   * Get moderation case by ID
   *
   * @param {string} caseId - Case ID
   * @returns {Promise<ModerationCase>}
   */
  async getCase(caseId) {}

  /**
   * Get pending cases for a reviewer
   *
   * @param {string} reviewerId - Reviewer user ID
   * @param {QueueFilter} filter - Queue filters
   * @returns {Promise<ModerationCase[]>}
   */
  async getPendingCases(reviewerId, filter = {}) {}

  /**
   * Assign case to reviewer
   *
   * @param {string} caseId - Case ID
   * @param {string} reviewerId - Reviewer ID
   * @returns {Promise<ModerationCase>}
   */
  async assignCase(caseId, reviewerId) {}

  /**
   * Submit review decision
   *
   * @param {string} caseId - Case ID
   * @param {ReviewDecision} decision - Review decision
   * @returns {Promise<ModerationCase>}
   */
  async submitDecision(caseId, decision) {}

  /**
   * Escalate case to senior reviewer
   *
   * @param {string} caseId - Case ID
   * @param {string} reason - Escalation reason
   * @returns {Promise<ModerationCase>}
   */
  async escalateCase(caseId, reason) {}

  /**
   * Get queue statistics
   *
   * @returns {Promise<QueueStats>}
   */
  async getQueueStats() {}
}

/**
 * ContentPrescreener
 *
 * Automated content pre-screening using rules and ML signals.
 */
class ContentPrescreener {
  /**
   * @param {Object} options - Configuration
   * @param {PrescreenRule[]} options.rules - Screening rules
   */
  constructor(options) {}

  /**
   * Pre-screen content before human review
   *
   * @param {string} videoId - Video ID
   * @param {VideoMetadata} metadata - Video metadata
   * @returns {Promise<PrescreenResult>}
   */
  async prescreen(videoId, metadata) {}

  /**
   * Check content against policy rules
   *
   * @param {VideoMetadata} metadata - Video metadata
   * @returns {Promise<RuleViolation[]>}
   */
  async checkPolicyRules(metadata) {}

  /**
   * Analyze thumbnail for policy compliance
   *
   * @param {string} thumbnailUrl - Thumbnail URL
   * @returns {Promise<ThumbnailAnalysis>}
   */
  async analyzeThumbnail(thumbnailUrl) {}

  /**
   * Score content risk level
   *
   * @param {VideoMetadata} metadata - Video metadata
   * @param {RuleViolation[]} violations - Detected violations
   * @returns {number} Risk score 0.0-1.0
   */
  calculateRiskScore(metadata, violations) {}

  /**
   * Add custom pre-screen rule
   *
   * @param {PrescreenRule} rule - Rule definition
   * @returns {void}
   */
  addRule(rule) {}
}

/**
 * ReviewWorkflowManager
 *
 * Manages human review workflows and SLAs.
 */
class ReviewWorkflowManager {
  /**
   * @param {Object} options - Configuration
   * @param {Object} options.slaConfig - SLA configuration
   */
  constructor(options) {}

  /**
   * Start review session for a case
   *
   * @param {string} caseId - Case ID
   * @param {string} reviewerId - Reviewer ID
   * @returns {Promise<ReviewSession>}
   */
  async startReviewSession(caseId, reviewerId) {}

  /**
   * End review session
   *
   * @param {string} sessionId - Session ID
   * @param {ReviewOutcome} outcome - Session outcome
   * @returns {Promise<ReviewSession>}
   */
  async endReviewSession(sessionId, outcome) {}

  /**
   * Check SLA status for pending cases
   *
   * @returns {Promise<SLAStatus[]>}
   */
  async checkSLAStatus() {}

  /**
   * Get reviewer performance metrics
   *
   * @param {string} reviewerId - Reviewer ID
   * @param {DateRange} dateRange - Date range
   * @returns {Promise<ReviewerMetrics>}
   */
  async getReviewerMetrics(reviewerId, dateRange) {}

  /**
   * Auto-assign cases based on reviewer availability and expertise
   *
   * @param {ModerationCase[]} cases - Cases to assign
   * @param {Reviewer[]} reviewers - Available reviewers
   * @returns {Promise<Assignment[]>}
   */
  async autoAssignCases(cases, reviewers) {}
}

/**
 * EnforcementActionHandler
 *
 * Executes enforcement actions based on moderation decisions.
 */
class EnforcementActionHandler {
  /**
   * @param {Object} options - Configuration
   * @param {Object} options.catalogClient - Catalog service client
   * @param {Object} options.userClient - User service client
   * @param {Object} options.eventBus - Event bus
   */
  constructor(options) {}

  /**
   * Execute enforcement action
   *
   * @param {EnforcementAction} action - Action to execute
   * @returns {Promise<EnforcementResult>}
   */
  async executeAction(action) {}

  /**
   * Remove video from platform
   *
   * @param {string} videoId - Video ID
   * @param {string} reason - Removal reason
   * @returns {Promise<void>}
   */
  async removeVideo(videoId, reason) {}

  /**
   * Age-restrict video
   *
   * @param {string} videoId - Video ID
   * @returns {Promise<void>}
   */
  async ageRestrictVideo(videoId) {}

  /**
   * Issue warning to creator
   *
   * @param {string} userId - Creator user ID
   * @param {string} videoId - Video ID
   * @param {ViolationType} violationType - Type of violation
   * @returns {Promise<Warning>}
   */
  async issueWarning(userId, videoId, violationType) {}

  /**
   * Apply strike to creator account
   *
   * @param {string} userId - Creator user ID
   * @param {string} videoId - Video ID
   * @param {ViolationType} violationType - Type of violation
   * @returns {Promise<Strike>}
   */
  async applyStrike(userId, videoId, violationType) {}

  /**
   * Check creator strike history
   *
   * @param {string} userId - Creator user ID
   * @returns {Promise<StrikeHistory>}
   */
  async getStrikeHistory(userId) {}

  /**
   * Appeal enforcement action
   *
   * @param {string} actionId - Action ID
   * @param {AppealRequest} appeal - Appeal request
   * @returns {Promise<Appeal>}
   */
  async submitAppeal(actionId, appeal) {}
}
```

### Data Structures

```javascript
/**
 * @typedef {Object} ModerationSubmission
 * @property {string} videoId - Video ID
 * @property {string} submitterId - Who submitted (system or user)
 * @property {SubmissionSource} source - Submission source
 * @property {string} reason - Reason for submission
 * @property {number} priority - Priority level 1-5
 */

/**
 * @typedef {'upload' | 'user_report' | 'automated' | 'appeal'} SubmissionSource
 */

/**
 * @typedef {Object} ModerationCase
 * @property {string} id - Case ID
 * @property {string} videoId - Video ID
 * @property {CaseStatus} status - Current status
 * @property {number} priority - Priority 1-5
 * @property {string} assignedTo - Assigned reviewer ID
 * @property {PrescreenResult} prescreenResult - Pre-screening result
 * @property {ReviewDecision[]} decisions - Review decisions history
 * @property {EnforcementAction[]} actions - Applied actions
 * @property {Date} createdAt
 * @property {Date} updatedAt
 * @property {Date} slaDeadline
 */

/**
 * @typedef {'pending' | 'in_review' | 'escalated' | 'decided' | 'appealed' | 'closed'} CaseStatus
 */

/**
 * @typedef {Object} ReviewDecision
 * @property {string} reviewerId - Reviewer ID
 * @property {DecisionType} decision - Decision type
 * @property {ViolationType[]} violations - Detected violations
 * @property {string} notes - Reviewer notes
 * @property {number} confidence - Confidence level 0.0-1.0
 * @property {Date} timestamp
 */

/**
 * @typedef {'approve' | 'reject' | 'age_restrict' | 'needs_edit' | 'escalate'} DecisionType
 */

/**
 * @typedef {'spam' | 'harassment' | 'hate_speech' | 'violence' | 'nudity' |
 *           'copyright' | 'misinformation' | 'dangerous' | 'other'} ViolationType
 */

/**
 * @typedef {Object} PrescreenResult
 * @property {boolean} autoApproved - Auto-approved by prescreener
 * @property {boolean} autoRejected - Auto-rejected by prescreener
 * @property {number} riskScore - Risk score 0.0-1.0
 * @property {RuleViolation[]} violations - Detected violations
 * @property {string[]} flags - Warning flags
 * @property {Object} mlSignals - ML model signals
 */

/**
 * @typedef {Object} RuleViolation
 * @property {string} ruleId - Rule ID
 * @property {string} ruleName - Rule name
 * @property {ViolationType} type - Violation type
 * @property {number} severity - Severity 1-5
 * @property {string} evidence - Evidence description
 */

/**
 * @typedef {Object} PrescreenRule
 * @property {string} id - Rule ID
 * @property {string} name - Rule name
 * @property {ViolationType} type - Violation type
 * @property {Object} conditions - Rule conditions
 * @property {number} priority - Evaluation priority
 * @property {boolean} autoReject - Auto-reject on match
 */

/**
 * @typedef {Object} QueueFilter
 * @property {CaseStatus[]} statuses - Filter by status
 * @property {number} minPriority - Minimum priority
 * @property {ViolationType[]} violationTypes - Filter by violation type
 * @property {DateRange} dateRange - Date range filter
 */

/**
 * @typedef {Object} QueueStats
 * @property {number} pending - Pending cases
 * @property {number} inReview - Cases in review
 * @property {number} escalated - Escalated cases
 * @property {number} decidedToday - Decided today
 * @property {number} avgReviewTime - Average review time in seconds
 * @property {Object} byViolationType - Count by violation type
 */

/**
 * @typedef {Object} EnforcementAction
 * @property {string} id - Action ID
 * @property {string} caseId - Related case ID
 * @property {ActionType} type - Action type
 * @property {string} targetId - Target (video or user ID)
 * @property {string} reason - Action reason
 * @property {Date} executedAt
 * @property {string} executedBy - Executor ID
 */

/**
 * @typedef {'remove' | 'age_restrict' | 'warning' | 'strike' | 'suspend' | 'terminate'} ActionType
 */

/**
 * @typedef {Object} ReviewerMetrics
 * @property {string} reviewerId
 * @property {number} casesReviewed
 * @property {number} avgReviewTime
 * @property {number} accuracyRate
 * @property {number} escalationRate
 * @property {Object} decisionBreakdown
 */
```

### Architectural Requirements

1. **Event-driven**: Subscribe to `video.uploaded` event to auto-queue content
2. **Priority queue**: Use RabbitMQ with priority queues for case assignment
3. **Audit logging**: Log all moderation actions for compliance
4. **Multi-reviewer support**: Support second opinion and escalation workflows
5. **Port**: 3012

### Acceptance Criteria

1. **Unit tests** (minimum 35 tests in `tests/unit/moderation/`):
   - Pre-screening rule evaluation
   - Risk score calculation
   - Case state machine transitions
   - SLA deadline calculation
   - Strike accumulation logic

2. **Integration tests** (minimum 20 tests in `tests/integration/moderation.test.js`):
   - Full moderation workflow
   - Event consumption (video.uploaded)
   - Enforcement action execution
   - Appeal workflow

3. **Security tests** (minimum 5 tests in `tests/security/moderation.test.js`):
   - Reviewer authorization
   - Audit log integrity
   - Action authorization

4. **Test command**: `npm test -- --testPathPattern=moderation`

---

## General Guidelines

### Code Style

Follow existing patterns in the codebase:
- Use ES6+ features (async/await, destructuring, arrow functions)
- JSDoc comments for all public methods
- Error handling with descriptive messages
- Consistent naming conventions

### Testing Patterns

Follow Jest patterns from `tests/`:
- Use `beforeEach` for test isolation
- Mock external dependencies with `jest.mock()`
- Use `global.testUtils` helpers from `tests/setup.js`
- Group related tests with `describe` blocks

### Integration Points

Each new service must integrate with:
- **EventBus** (`shared/events/`) - Publish/subscribe events
- **ServiceClient** (`shared/clients/`) - Inter-service communication
- **Health endpoint** - `GET /health` returning `{ status: 'healthy', service: '<name>' }`

### Running Tests

```bash
# Run all tests
npm test

# Run tests for specific service
npm test -- --testPathPattern=content-recommender
npm test -- --testPathPattern=clip-generator
npm test -- --testPathPattern=moderation

# Run with coverage
npm test -- --coverage --testPathPattern=<service>
```

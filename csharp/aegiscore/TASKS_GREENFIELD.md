# AegisCore - Greenfield Implementation Tasks

These tasks require implementing **new modules from scratch** that integrate with the existing AegisCore security platform. Each task provides an interface contract, required types, and acceptance criteria.

---

## Task 1: Threat Detection Engine

### Overview

Implement a real-time threat detection engine that analyzes security events, classifies threat severity, correlates related incidents, and triggers appropriate responses based on configurable detection rules.

### Interface Contract

```csharp
namespace AegisCore;

/// <summary>
/// Represents a security event captured by the platform.
/// </summary>
/// <param name="Id">Unique event identifier</param>
/// <param name="Source">Origin of the event (IP, service name, user ID)</param>
/// <param name="EventType">Type of security event (login_failure, port_scan, data_exfil, etc.)</param>
/// <param name="Timestamp">Unix timestamp when event occurred</param>
/// <param name="Payload">Raw event data as key-value pairs</param>
public record SecurityEvent(
    string Id,
    string Source,
    string EventType,
    long Timestamp,
    IReadOnlyDictionary<string, string> Payload);

/// <summary>
/// Represents a detected threat with severity and recommended actions.
/// </summary>
/// <param name="ThreatId">Unique threat identifier</param>
/// <param name="Severity">Threat severity level (1=Info to 5=Critical)</param>
/// <param name="Category">Threat category (brute_force, reconnaissance, exfiltration, etc.)</param>
/// <param name="CorrelatedEvents">List of event IDs that contributed to this threat</param>
/// <param name="RecommendedActions">Suggested response actions</param>
/// <param name="DetectedAt">Timestamp when threat was detected</param>
public record Threat(
    string ThreatId,
    int Severity,
    string Category,
    IReadOnlyList<string> CorrelatedEvents,
    IReadOnlyList<string> RecommendedActions,
    long DetectedAt);

/// <summary>
/// Configurable rule for detecting specific threat patterns.
/// </summary>
/// <param name="RuleId">Unique rule identifier</param>
/// <param name="EventType">Event type this rule matches</param>
/// <param name="Threshold">Number of events required to trigger</param>
/// <param name="WindowSeconds">Time window for event correlation</param>
/// <param name="Severity">Severity level when triggered</param>
/// <param name="Category">Threat category when triggered</param>
public record DetectionRule(
    string RuleId,
    string EventType,
    int Threshold,
    long WindowSeconds,
    int Severity,
    string Category);

/// <summary>
/// Core threat detection service interface.
/// </summary>
public interface IThreatDetector
{
    /// <summary>
    /// Ingests a security event for analysis.
    /// </summary>
    /// <param name="evt">The security event to analyze</param>
    /// <returns>A detected threat if the event triggers a rule, null otherwise</returns>
    Threat? Analyze(SecurityEvent evt);

    /// <summary>
    /// Registers a detection rule.
    /// </summary>
    /// <param name="rule">The rule to register</param>
    void RegisterRule(DetectionRule rule);

    /// <summary>
    /// Removes a detection rule by ID.
    /// </summary>
    /// <param name="ruleId">The rule ID to remove</param>
    /// <returns>True if rule was found and removed</returns>
    bool RemoveRule(string ruleId);

    /// <summary>
    /// Gets all registered detection rules.
    /// </summary>
    IReadOnlyList<DetectionRule> GetRules();

    /// <summary>
    /// Gets recent threats within a time window.
    /// </summary>
    /// <param name="since">Unix timestamp to filter threats from</param>
    IReadOnlyList<Threat> GetRecentThreats(long since);

    /// <summary>
    /// Correlates events from a specific source within a time window.
    /// </summary>
    /// <param name="source">The source to correlate events for</param>
    /// <param name="windowSeconds">Time window in seconds</param>
    /// <param name="now">Current timestamp</param>
    IReadOnlyList<SecurityEvent> CorrelateBySource(string source, long windowSeconds, long now);

    /// <summary>
    /// Computes threat score for a source based on recent activity.
    /// </summary>
    /// <param name="source">The source to score</param>
    /// <param name="now">Current timestamp</param>
    /// <returns>Score from 0.0 (safe) to 1.0 (high risk)</returns>
    double ComputeThreatScore(string source, long now);

    /// <summary>
    /// Clears expired events older than the retention period.
    /// </summary>
    /// <param name="now">Current timestamp</param>
    /// <param name="retentionSeconds">How long to retain events</param>
    /// <returns>Number of events purged</returns>
    int PurgeExpiredEvents(long now, long retentionSeconds);
}

/// <summary>
/// Static helper methods for threat classification.
/// </summary>
public static class ThreatClassifier
{
    /// <summary>
    /// Classifies event type into a threat category.
    /// </summary>
    public static string ClassifyCategory(string eventType);

    /// <summary>
    /// Suggests response actions based on threat severity and category.
    /// </summary>
    public static IReadOnlyList<string> SuggestActions(int severity, string category);

    /// <summary>
    /// Determines if a threat requires immediate escalation.
    /// </summary>
    public static bool RequiresEscalation(int severity, int eventCount);
}
```

### Required Classes

| Type | Description |
|------|-------------|
| `SecurityEvent` | Record for captured security events |
| `Threat` | Record for detected threats with correlation data |
| `DetectionRule` | Record for configurable detection rules |
| `ThreatDetector` | Main class implementing `IThreatDetector` |
| `ThreatClassifier` | Static helper for threat classification |

### Architectural Requirements

1. **Thread Safety**: All mutable state in `ThreatDetector` must be protected with locks (follow `TokenStore` pattern)
2. **Event Correlation**: Use sliding window for correlating events from the same source (follow `RollingWindowScheduler` pattern)
3. **Rule Engine**: Support multiple concurrent rules with O(1) lookup by event type
4. **Integration**: Should integrate with existing `Policy` module for escalation decisions

### Acceptance Criteria

- [ ] All interface methods implemented correctly
- [ ] Thread-safe implementation with proper locking
- [ ] Event correlation respects time windows
- [ ] Threat scoring algorithm produces values in [0.0, 1.0]
- [ ] Minimum 50 unit tests covering:
  - Single event analysis
  - Multi-event correlation triggering rules
  - Rule registration/removal
  - Threat score computation
  - Event purging
  - Edge cases (empty state, boundary thresholds)
- [ ] Integration test with `PolicyEngine` escalation
- [ ] Test command: `dotnet test`

---

## Task 2: Access Log Analyzer

### Overview

Implement an access log analyzer that tracks user sessions, detects anomalous access patterns, computes access statistics, and identifies potential security violations such as impossible travel or privilege escalation attempts.

### Interface Contract

```csharp
namespace AegisCore;

/// <summary>
/// Represents an access log entry.
/// </summary>
/// <param name="LogId">Unique log entry identifier</param>
/// <param name="UserId">User who performed the access</param>
/// <param name="Resource">Resource that was accessed</param>
/// <param name="Action">Action performed (read, write, delete, admin)</param>
/// <param name="Timestamp">Unix timestamp of access</param>
/// <param name="IpAddress">Source IP address</param>
/// <param name="GeoLocation">Optional geographic location (latitude, longitude)</param>
/// <param name="Success">Whether access was granted</param>
public record AccessLogEntry(
    string LogId,
    string UserId,
    string Resource,
    string Action,
    long Timestamp,
    string IpAddress,
    (double Lat, double Lon)? GeoLocation,
    bool Success);

/// <summary>
/// Represents an anomaly detected in access patterns.
/// </summary>
/// <param name="AnomalyId">Unique anomaly identifier</param>
/// <param name="UserId">User associated with the anomaly</param>
/// <param name="AnomalyType">Type of anomaly (impossible_travel, privilege_escalation, etc.)</param>
/// <param name="Severity">Severity from 1 (low) to 5 (critical)</param>
/// <param name="Description">Human-readable description</param>
/// <param name="RelatedLogs">Log entry IDs that contributed to this anomaly</param>
/// <param name="DetectedAt">Timestamp when anomaly was detected</param>
public record AccessAnomaly(
    string AnomalyId,
    string UserId,
    string AnomalyType,
    int Severity,
    string Description,
    IReadOnlyList<string> RelatedLogs,
    long DetectedAt);

/// <summary>
/// User access statistics summary.
/// </summary>
/// <param name="UserId">User identifier</param>
/// <param name="TotalAccesses">Total number of access attempts</param>
/// <param name="SuccessfulAccesses">Number of successful accesses</param>
/// <param name="FailedAccesses">Number of denied accesses</param>
/// <param name="UniqueResources">Count of distinct resources accessed</param>
/// <param name="UniqueIpAddresses">Count of distinct IP addresses used</param>
/// <param name="FirstSeen">Timestamp of first recorded access</param>
/// <param name="LastSeen">Timestamp of most recent access</param>
public record UserAccessStats(
    string UserId,
    int TotalAccesses,
    int SuccessfulAccesses,
    int FailedAccesses,
    int UniqueResources,
    int UniqueIpAddresses,
    long FirstSeen,
    long LastSeen);

/// <summary>
/// Configuration for anomaly detection thresholds.
/// </summary>
/// <param name="ImpossibleTravelSpeedKmH">Max travel speed before flagging (default 1000 km/h)</param>
/// <param name="FailedAccessThreshold">Failed accesses before alerting</param>
/// <param name="FailedAccessWindowSeconds">Time window for failed access counting</param>
/// <param name="PrivilegeEscalationActions">Actions considered privileged</param>
public record AnomalyConfig(
    double ImpossibleTravelSpeedKmH,
    int FailedAccessThreshold,
    long FailedAccessWindowSeconds,
    IReadOnlySet<string> PrivilegeEscalationActions);

/// <summary>
/// Core access log analyzer interface.
/// </summary>
public interface IAccessLogAnalyzer
{
    /// <summary>
    /// Records an access log entry and checks for anomalies.
    /// </summary>
    /// <param name="entry">The log entry to record</param>
    /// <returns>An anomaly if detected, null otherwise</returns>
    AccessAnomaly? RecordAccess(AccessLogEntry entry);

    /// <summary>
    /// Gets access statistics for a specific user.
    /// </summary>
    /// <param name="userId">The user ID to query</param>
    UserAccessStats? GetUserStats(string userId);

    /// <summary>
    /// Gets all detected anomalies within a time range.
    /// </summary>
    /// <param name="from">Start timestamp (inclusive)</param>
    /// <param name="to">End timestamp (inclusive)</param>
    IReadOnlyList<AccessAnomaly> GetAnomalies(long from, long to);

    /// <summary>
    /// Gets access logs for a specific user within a time range.
    /// </summary>
    /// <param name="userId">User to query</param>
    /// <param name="from">Start timestamp</param>
    /// <param name="to">End timestamp</param>
    IReadOnlyList<AccessLogEntry> GetUserLogs(string userId, long from, long to);

    /// <summary>
    /// Gets access logs for a specific resource.
    /// </summary>
    /// <param name="resource">Resource path to query</param>
    IReadOnlyList<AccessLogEntry> GetResourceLogs(string resource);

    /// <summary>
    /// Checks if a user's current session shows signs of compromise.
    /// </summary>
    /// <param name="userId">User to check</param>
    /// <param name="now">Current timestamp</param>
    bool IsSessionCompromised(string userId, long now);

    /// <summary>
    /// Gets the top N most accessed resources.
    /// </summary>
    /// <param name="topN">Number of resources to return</param>
    IReadOnlyList<(string Resource, int AccessCount)> GetTopResources(int topN);

    /// <summary>
    /// Clears logs older than the retention period.
    /// </summary>
    /// <param name="now">Current timestamp</param>
    /// <param name="retentionSeconds">Retention period</param>
    /// <returns>Number of logs purged</returns>
    int PurgeLogs(long now, long retentionSeconds);
}

/// <summary>
/// Static helpers for geo-distance and travel calculations.
/// </summary>
public static class GeoAnalyzer
{
    /// <summary>
    /// Calculates distance between two points in kilometers using Haversine formula.
    /// </summary>
    public static double DistanceKm(double lat1, double lon1, double lat2, double lon2);

    /// <summary>
    /// Determines if travel between two points in the given time is physically possible.
    /// </summary>
    public static bool IsTravelPossible(
        (double Lat, double Lon) from,
        (double Lat, double Lon) to,
        long elapsedSeconds,
        double maxSpeedKmH);

    /// <summary>
    /// Estimates travel time between two points assuming max speed.
    /// </summary>
    public static double EstimateTravelHours(double distanceKm, double speedKmH);
}
```

### Required Classes

| Type | Description |
|------|-------------|
| `AccessLogEntry` | Record for individual access log entries |
| `AccessAnomaly` | Record for detected anomalies |
| `UserAccessStats` | Record for aggregated user statistics |
| `AnomalyConfig` | Record for detection configuration |
| `AccessLogAnalyzer` | Main class implementing `IAccessLogAnalyzer` |
| `GeoAnalyzer` | Static helper for geographic calculations |

### Architectural Requirements

1. **Thread Safety**: Use locking pattern consistent with `WorkflowEngine`
2. **Index Structures**: Maintain efficient lookups by user ID and resource
3. **Statistics**: Use patterns from `Statistics` module for percentile/mean calculations
4. **Integration**: Anomalies should be reportable to `ThreatDetector` (Task 1) if both implemented

### Acceptance Criteria

- [ ] All interface methods implemented correctly
- [ ] Haversine distance calculation accurate to within 1%
- [ ] Impossible travel detection working for realistic scenarios
- [ ] Failed access threshold alerting functional
- [ ] Minimum 50 unit tests covering:
  - Log recording and retrieval
  - User statistics computation
  - Impossible travel detection
  - Failed access threshold detection
  - Top resources ranking
  - Log purging
  - Edge cases (no geo data, same location accesses)
- [ ] Integration test demonstrating anomaly escalation to `PolicyEngine`
- [ ] Test command: `dotnet test`

---

## Task 3: Secret Rotation Service

### Overview

Implement a secret rotation service that manages credentials, API keys, and certificates with automatic rotation schedules, secure storage, audit logging, and integration with the existing `TokenStore` and `Security` modules.

### Interface Contract

```csharp
namespace AegisCore;

/// <summary>
/// Types of secrets managed by the rotation service.
/// </summary>
public enum SecretType
{
    ApiKey,
    DatabaseCredential,
    Certificate,
    EncryptionKey,
    ServiceToken
}

/// <summary>
/// Represents a managed secret with rotation metadata.
/// </summary>
/// <param name="SecretId">Unique secret identifier</param>
/// <param name="Name">Human-readable name</param>
/// <param name="Type">Type of secret</param>
/// <param name="CreatedAt">Timestamp when secret was created</param>
/// <param name="ExpiresAt">Timestamp when secret expires</param>
/// <param name="RotationIntervalSeconds">How often to rotate</param>
/// <param name="LastRotatedAt">When the secret was last rotated</param>
/// <param name="Version">Current version number</param>
/// <param name="IsActive">Whether the secret is currently active</param>
public record ManagedSecret(
    string SecretId,
    string Name,
    SecretType Type,
    long CreatedAt,
    long ExpiresAt,
    long RotationIntervalSeconds,
    long LastRotatedAt,
    int Version,
    bool IsActive);

/// <summary>
/// Result of a rotation operation.
/// </summary>
/// <param name="Success">Whether rotation succeeded</param>
/// <param name="SecretId">ID of the rotated secret</param>
/// <param name="OldVersion">Previous version number</param>
/// <param name="NewVersion">New version number</param>
/// <param name="Error">Error message if failed</param>
public record RotationResult(
    bool Success,
    string SecretId,
    int OldVersion,
    int NewVersion,
    string? Error);

/// <summary>
/// Audit entry for secret operations.
/// </summary>
/// <param name="AuditId">Unique audit entry identifier</param>
/// <param name="SecretId">Secret that was accessed/modified</param>
/// <param name="Operation">Operation performed (create, read, rotate, revoke)</param>
/// <param name="PerformedBy">Identity that performed the operation</param>
/// <param name="Timestamp">When the operation occurred</param>
/// <param name="Success">Whether the operation succeeded</param>
/// <param name="Details">Additional operation details</param>
public record SecretAuditEntry(
    string AuditId,
    string SecretId,
    string Operation,
    string PerformedBy,
    long Timestamp,
    bool Success,
    string? Details);

/// <summary>
/// Configuration for the secret rotation service.
/// </summary>
/// <param name="DefaultRotationIntervalSeconds">Default rotation interval for new secrets</param>
/// <param name="GracePeriodSeconds">How long old versions remain valid after rotation</param>
/// <param name="MaxVersionsToRetain">How many old versions to keep</param>
/// <param name="AutoRotateEnabled">Whether automatic rotation is enabled</param>
public record RotationConfig(
    long DefaultRotationIntervalSeconds,
    long GracePeriodSeconds,
    int MaxVersionsToRetain,
    bool AutoRotateEnabled);

/// <summary>
/// Delegate for generating new secret values.
/// </summary>
public delegate string SecretGenerator(SecretType type, int version);

/// <summary>
/// Core secret rotation service interface.
/// </summary>
public interface ISecretRotationService
{
    /// <summary>
    /// Registers a new managed secret.
    /// </summary>
    /// <param name="name">Human-readable name</param>
    /// <param name="type">Type of secret</param>
    /// <param name="initialValue">Initial secret value</param>
    /// <param name="rotationIntervalSeconds">Rotation interval (0 for no rotation)</param>
    /// <param name="performedBy">Identity creating the secret</param>
    /// <returns>The created managed secret metadata</returns>
    ManagedSecret Register(
        string name,
        SecretType type,
        string initialValue,
        long rotationIntervalSeconds,
        string performedBy);

    /// <summary>
    /// Retrieves the current value of a secret.
    /// </summary>
    /// <param name="secretId">Secret identifier</param>
    /// <param name="performedBy">Identity requesting the secret</param>
    /// <returns>The secret value, or null if not found or revoked</returns>
    string? GetValue(string secretId, string performedBy);

    /// <summary>
    /// Rotates a secret to a new value.
    /// </summary>
    /// <param name="secretId">Secret to rotate</param>
    /// <param name="generator">Function to generate new value</param>
    /// <param name="performedBy">Identity performing rotation</param>
    /// <returns>Result of the rotation operation</returns>
    RotationResult Rotate(string secretId, SecretGenerator generator, string performedBy);

    /// <summary>
    /// Revokes a secret, making it permanently inactive.
    /// </summary>
    /// <param name="secretId">Secret to revoke</param>
    /// <param name="performedBy">Identity performing revocation</param>
    /// <returns>True if revoked, false if not found</returns>
    bool Revoke(string secretId, string performedBy);

    /// <summary>
    /// Gets metadata for a managed secret.
    /// </summary>
    /// <param name="secretId">Secret identifier</param>
    ManagedSecret? GetMetadata(string secretId);

    /// <summary>
    /// Gets all secrets that need rotation based on their schedule.
    /// </summary>
    /// <param name="now">Current timestamp</param>
    IReadOnlyList<ManagedSecret> GetSecretsNeedingRotation(long now);

    /// <summary>
    /// Gets all secrets expiring within a time window.
    /// </summary>
    /// <param name="now">Current timestamp</param>
    /// <param name="windowSeconds">Lookahead window</param>
    IReadOnlyList<ManagedSecret> GetExpiringSecrets(long now, long windowSeconds);

    /// <summary>
    /// Validates a secret value against stored value (constant-time comparison).
    /// </summary>
    /// <param name="secretId">Secret identifier</param>
    /// <param name="value">Value to validate</param>
    /// <returns>True if valid, false otherwise</returns>
    bool Validate(string secretId, string value);

    /// <summary>
    /// Gets audit log entries for a secret.
    /// </summary>
    /// <param name="secretId">Secret to query</param>
    IReadOnlyList<SecretAuditEntry> GetAuditLog(string secretId);

    /// <summary>
    /// Gets all audit entries within a time range.
    /// </summary>
    /// <param name="from">Start timestamp</param>
    /// <param name="to">End timestamp</param>
    IReadOnlyList<SecretAuditEntry> GetAuditLogRange(long from, long to);

    /// <summary>
    /// Performs automatic rotation for all secrets that need it.
    /// </summary>
    /// <param name="now">Current timestamp</param>
    /// <param name="generator">Generator for new values</param>
    /// <param name="performedBy">Identity for audit</param>
    /// <returns>List of rotation results</returns>
    IReadOnlyList<RotationResult> AutoRotate(long now, SecretGenerator generator, string performedBy);

    /// <summary>
    /// Gets count of active secrets by type.
    /// </summary>
    IReadOnlyDictionary<SecretType, int> GetSecretCountsByType();
}

/// <summary>
/// Static helpers for secret generation and validation.
/// </summary>
public static class SecretHelpers
{
    /// <summary>
    /// Generates a cryptographically secure random string.
    /// </summary>
    /// <param name="length">Length of string to generate</param>
    public static string GenerateRandomString(int length);

    /// <summary>
    /// Generates a default secret value based on type.
    /// </summary>
    public static string GenerateDefault(SecretType type, int version);

    /// <summary>
    /// Validates secret name format (alphanumeric, underscores, hyphens).
    /// </summary>
    public static bool IsValidName(string name);

    /// <summary>
    /// Computes a digest of the secret for logging (never log actual values).
    /// </summary>
    public static string ComputeDigest(string value);
}
```

### Required Classes

| Type | Description |
|------|-------------|
| `SecretType` | Enum for secret classification |
| `ManagedSecret` | Record for secret metadata |
| `RotationResult` | Record for rotation operation results |
| `SecretAuditEntry` | Record for audit logging |
| `RotationConfig` | Record for service configuration |
| `SecretGenerator` | Delegate for value generation |
| `SecretRotationService` | Main class implementing `ISecretRotationService` |
| `SecretHelpers` | Static helper methods |

### Architectural Requirements

1. **Thread Safety**: Use locking pattern consistent with `TokenStore`
2. **Constant-Time Comparison**: Use `CryptographicOperations.FixedTimeEquals` for validation (follow `Security` pattern)
3. **Audit Trail**: Every operation must be logged with full context
4. **Integration**: Validate method should use `Security.Digest` for hashing; integrate with `TokenStore` for token-based secrets
5. **No Plain-Text Logging**: Never log actual secret values, only digests

### Acceptance Criteria

- [ ] All interface methods implemented correctly
- [ ] Constant-time comparison for secret validation
- [ ] Complete audit trail for all operations
- [ ] Automatic rotation respects schedules and grace periods
- [ ] Minimum 60 unit tests covering:
  - Secret registration and retrieval
  - Manual rotation
  - Automatic rotation batch processing
  - Secret revocation
  - Audit log queries
  - Expiration detection
  - Validation with constant-time comparison
  - Edge cases (revoked secrets, expired secrets, concurrent access)
- [ ] Integration test with existing `Security` and `TokenStore` modules
- [ ] No secret values in test output or logs
- [ ] Test command: `dotnet test`

---

## General Requirements

All greenfield implementations must:

1. **Follow existing patterns**: Study `Resilience.cs`, `Security.cs`, and `Workflow.cs` for architectural guidance
2. **Use records for immutable data**: All DTOs should be records with init-only properties
3. **Implement thread safety**: Use `lock` with private objects for all mutable state
4. **Provide XML documentation**: All public types and members must have `<summary>` docs
5. **Handle edge cases**: Empty inputs, null checks, boundary conditions
6. **Integrate with existing modules**: Reference and use existing types where appropriate

## Test Organization

Create tests in `tests/AegisCore.Tests/` following existing patterns:

```
tests/AegisCore.Tests/
    ThreatDetectorTests.cs      # Task 1 tests
    AccessLogAnalyzerTests.cs   # Task 2 tests
    SecretRotationTests.cs      # Task 3 tests
```

Use xUnit with `[Fact]` and `[Theory]` attributes as seen in `CoreTests.cs`.

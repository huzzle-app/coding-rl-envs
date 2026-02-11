# StrataGuard Greenfield Tasks

This document defines greenfield implementation tasks for the StrataGuard security/protection platform. Each task requires implementing a new module from scratch while following existing architectural patterns.

---

## Task 1: Intrusion Detection Service

### Overview

Implement an intrusion detection service that monitors system events, identifies suspicious patterns, and raises security alerts. The service must integrate with the existing `Security`, `Policy`, and `QueueGuard` modules.

### Interface Contract

```csharp
namespace StrataGuard;

/// <summary>
/// Represents a detected intrusion or suspicious activity.
/// </summary>
/// <param name="Id">Unique identifier for the detection event.</param>
/// <param name="SourceIp">IP address of the detected threat source.</param>
/// <param name="TargetService">The service being targeted.</param>
/// <param name="ThreatLevel">Severity level (1-5, matching Severity constants).</param>
/// <param name="Signature">Pattern signature that triggered the detection.</param>
/// <param name="Timestamp">Unix timestamp when detected.</param>
public record IntrusionEvent(
    string Id,
    string SourceIp,
    string TargetService,
    int ThreatLevel,
    string Signature,
    long Timestamp);

/// <summary>
/// Detection rule for identifying intrusion patterns.
/// </summary>
/// <param name="Id">Unique rule identifier.</param>
/// <param name="Pattern">Regex or signature pattern to match.</param>
/// <param name="ThreatLevel">Severity when this rule triggers.</param>
/// <param name="Enabled">Whether the rule is active.</param>
public record DetectionRule(string Id, string Pattern, int ThreatLevel, bool Enabled);

/// <summary>
/// Static utility methods for intrusion detection analysis.
/// </summary>
public static class IntrusionDetection
{
    /// <summary>
    /// Analyzes a sequence of events and identifies potential intrusions.
    /// </summary>
    /// <param name="events">Raw system events to analyze.</param>
    /// <param name="rules">Detection rules to apply.</param>
    /// <returns>List of detected intrusion events.</returns>
    public static IReadOnlyList<IntrusionEvent> Analyze(
        IEnumerable<SystemEvent> events,
        IReadOnlyList<DetectionRule> rules);

    /// <summary>
    /// Calculates the threat score for a source IP based on recent activity.
    /// </summary>
    /// <param name="events">Intrusion events from this source.</param>
    /// <param name="decayFactor">Time decay factor (0.0-1.0).</param>
    /// <param name="now">Current timestamp.</param>
    /// <returns>Cumulative threat score.</returns>
    public static double ThreatScore(
        IReadOnlyList<IntrusionEvent> events,
        double decayFactor,
        long now);

    /// <summary>
    /// Determines if an IP should be blocked based on threat history.
    /// </summary>
    /// <param name="events">Historical intrusion events.</param>
    /// <param name="threshold">Blocking threshold score.</param>
    /// <param name="windowSeconds">Time window to consider.</param>
    /// <param name="now">Current timestamp.</param>
    /// <returns>True if IP should be blocked.</returns>
    public static bool ShouldBlock(
        IReadOnlyList<IntrusionEvent> events,
        double threshold,
        long windowSeconds,
        long now);

    /// <summary>
    /// Groups intrusion events by attack pattern/signature.
    /// </summary>
    /// <param name="events">Events to group.</param>
    /// <returns>Dictionary mapping signature to event list.</returns>
    public static IReadOnlyDictionary<string, IReadOnlyList<IntrusionEvent>> GroupBySignature(
        IEnumerable<IntrusionEvent> events);

    /// <summary>
    /// Calculates the rate of intrusion attempts per minute.
    /// </summary>
    /// <param name="events">Intrusion events.</param>
    /// <param name="windowMinutes">Time window in minutes.</param>
    /// <param name="now">Current timestamp.</param>
    /// <returns>Attempts per minute.</returns>
    public static double AttackRate(
        IReadOnlyList<IntrusionEvent> events,
        int windowMinutes,
        long now);

    /// <summary>
    /// Identifies the top N most targeted services.
    /// </summary>
    /// <param name="events">Intrusion events to analyze.</param>
    /// <param name="topN">Number of services to return.</param>
    /// <returns>List of (service, count) tuples ordered by count descending.</returns>
    public static IReadOnlyList<(string Service, int Count)> TopTargets(
        IEnumerable<IntrusionEvent> events,
        int topN);

    /// <summary>
    /// Correlates events to detect coordinated attacks from multiple sources.
    /// </summary>
    /// <param name="events">Events to analyze.</param>
    /// <param name="timeWindowMs">Time window for correlation.</param>
    /// <returns>List of correlated event groups.</returns>
    public static IReadOnlyList<IReadOnlyList<IntrusionEvent>> CorrelateAttacks(
        IEnumerable<IntrusionEvent> events,
        long timeWindowMs);
}

/// <summary>
/// Raw system event for intrusion analysis.
/// </summary>
/// <param name="Id">Event identifier.</param>
/// <param name="SourceIp">Source IP address.</param>
/// <param name="TargetService">Target service name.</param>
/// <param name="Payload">Event payload/data.</param>
/// <param name="Timestamp">Event timestamp.</param>
public record SystemEvent(
    string Id,
    string SourceIp,
    string TargetService,
    string Payload,
    long Timestamp);

/// <summary>
/// Thread-safe intrusion event store with time-based cleanup.
/// </summary>
public sealed class IntrusionStore
{
    /// <summary>
    /// Creates a new intrusion store.
    /// </summary>
    /// <param name="retentionSeconds">How long to retain events.</param>
    public IntrusionStore(long retentionSeconds);

    /// <summary>
    /// Records a new intrusion event.
    /// </summary>
    /// <param name="ev">The intrusion event to store.</param>
    public void Record(IntrusionEvent ev);

    /// <summary>
    /// Retrieves all events for a specific source IP.
    /// </summary>
    /// <param name="sourceIp">The source IP to query.</param>
    /// <returns>List of events from this source.</returns>
    public IReadOnlyList<IntrusionEvent> GetBySource(string sourceIp);

    /// <summary>
    /// Retrieves all events targeting a specific service.
    /// </summary>
    /// <param name="targetService">The target service to query.</param>
    /// <returns>List of events targeting this service.</returns>
    public IReadOnlyList<IntrusionEvent> GetByTarget(string targetService);

    /// <summary>
    /// Removes events older than retention period.
    /// </summary>
    /// <param name="now">Current timestamp.</param>
    /// <returns>Number of events removed.</returns>
    public int Cleanup(long now);

    /// <summary>
    /// Gets the total number of stored events.
    /// </summary>
    public int Count { get; }

    /// <summary>
    /// Gets all stored events.
    /// </summary>
    /// <returns>All intrusion events.</returns>
    public IReadOnlyList<IntrusionEvent> All();
}
```

### Required Classes/Records

| Type | Purpose |
|------|---------|
| `IntrusionEvent` | Immutable record for detected intrusions |
| `DetectionRule` | Configuration for pattern matching rules |
| `SystemEvent` | Raw input event for analysis |
| `IntrusionDetection` | Static utility class with analysis methods |
| `IntrusionStore` | Thread-safe event storage with retention |

### Architectural Patterns to Follow

1. **Static utility classes** - Follow `Security`, `Routing`, and `Statistics` patterns for stateless operations
2. **Thread-safe stores** - Follow `TokenStore`, `CheckpointManager` patterns with `lock (_lock)` guards
3. **Record types** - Use immutable records for data transfer (like `Route`, `Checkpoint`, `QueueItem`)
4. **Deterministic ordering** - When returning lists, use `.OrderBy()` chains for determinism (like `Resilience.Replay`)
5. **Input validation** - Handle edge cases (empty collections, zero/negative values) gracefully

### Acceptance Criteria

1. **Unit Tests**: Create `tests/StrataGuard.Tests/IntrusionTests.cs` with at least 15 test methods covering:
   - Event analysis with multiple rules
   - Threat score calculation with time decay
   - Blocking decision logic
   - Attack rate calculation
   - Signature grouping
   - Coordinated attack detection
   - Store operations (record, query, cleanup)
   - Edge cases (empty inputs, boundary conditions)

2. **Integration Points**:
   - Use `Security.Digest()` for generating event hashes
   - Integrate with `Severity` constants for threat levels
   - Compatible with `Policy.NextPolicy()` for automatic policy escalation

3. **Code Coverage**: Minimum 80% line coverage for new code

4. **Test Command**:
   ```bash
   dotnet test --filter "FullyQualifiedName~IntrusionTests"
   ```

---

## Task 2: Compliance Audit Logger

### Overview

Implement a compliance audit logging service that records security-relevant actions, generates audit reports, and validates compliance with security policies. The service must integrate with `Security`, `Policy`, and `Workflow` modules.

### Interface Contract

```csharp
namespace StrataGuard;

/// <summary>
/// Represents an auditable action in the system.
/// </summary>
/// <param name="Id">Unique audit entry identifier.</param>
/// <param name="Actor">User or service that performed the action.</param>
/// <param name="Action">Type of action performed.</param>
/// <param name="Resource">Resource that was acted upon.</param>
/// <param name="Outcome">Success, failure, or denied.</param>
/// <param name="Timestamp">When the action occurred.</param>
/// <param name="Metadata">Additional context as key-value pairs.</param>
public record AuditEntry(
    string Id,
    string Actor,
    string Action,
    string Resource,
    string Outcome,
    long Timestamp,
    IReadOnlyDictionary<string, string> Metadata);

/// <summary>
/// Compliance rule definition.
/// </summary>
/// <param name="Id">Rule identifier (e.g., "SOC2-CC6.1").</param>
/// <param name="Description">Human-readable description.</param>
/// <param name="RequiredActions">Actions that must be audited.</param>
/// <param name="RetentionDays">Minimum log retention period.</param>
public record ComplianceRule(
    string Id,
    string Description,
    IReadOnlyList<string> RequiredActions,
    int RetentionDays);

/// <summary>
/// Result of a compliance validation check.
/// </summary>
/// <param name="RuleId">The rule that was checked.</param>
/// <param name="Compliant">Whether the system is compliant.</param>
/// <param name="Findings">List of specific findings/issues.</param>
/// <param name="CheckedAt">Timestamp of the check.</param>
public record ComplianceResult(
    string RuleId,
    bool Compliant,
    IReadOnlyList<string> Findings,
    long CheckedAt);

/// <summary>
/// Static utility methods for compliance audit operations.
/// </summary>
public static class ComplianceAudit
{
    /// <summary>
    /// Generates a tamper-evident hash chain for a sequence of audit entries.
    /// Each entry's hash includes the previous entry's hash.
    /// </summary>
    /// <param name="entries">Audit entries to chain.</param>
    /// <returns>List of (entry, hash) tuples.</returns>
    public static IReadOnlyList<(AuditEntry Entry, string Hash)> BuildHashChain(
        IEnumerable<AuditEntry> entries);

    /// <summary>
    /// Verifies the integrity of an audit hash chain.
    /// </summary>
    /// <param name="chain">The hash chain to verify.</param>
    /// <returns>True if chain is intact, false if tampered.</returns>
    public static bool VerifyHashChain(
        IReadOnlyList<(AuditEntry Entry, string Hash)> chain);

    /// <summary>
    /// Validates compliance against a set of rules.
    /// </summary>
    /// <param name="entries">Audit log entries.</param>
    /// <param name="rules">Compliance rules to check.</param>
    /// <param name="now">Current timestamp.</param>
    /// <returns>Compliance results for each rule.</returns>
    public static IReadOnlyList<ComplianceResult> ValidateCompliance(
        IReadOnlyList<AuditEntry> entries,
        IReadOnlyList<ComplianceRule> rules,
        long now);

    /// <summary>
    /// Filters audit entries by time range.
    /// </summary>
    /// <param name="entries">All audit entries.</param>
    /// <param name="fromTimestamp">Start of range (inclusive).</param>
    /// <param name="toTimestamp">End of range (inclusive).</param>
    /// <returns>Filtered entries.</returns>
    public static IReadOnlyList<AuditEntry> FilterByTimeRange(
        IEnumerable<AuditEntry> entries,
        long fromTimestamp,
        long toTimestamp);

    /// <summary>
    /// Groups audit entries by actor for access review.
    /// </summary>
    /// <param name="entries">Audit entries to group.</param>
    /// <returns>Dictionary mapping actor to their actions.</returns>
    public static IReadOnlyDictionary<string, IReadOnlyList<AuditEntry>> GroupByActor(
        IEnumerable<AuditEntry> entries);

    /// <summary>
    /// Identifies privileged actions that require additional review.
    /// </summary>
    /// <param name="entries">Audit entries to analyze.</param>
    /// <returns>Entries containing privileged actions.</returns>
    public static IReadOnlyList<AuditEntry> FindPrivilegedActions(
        IEnumerable<AuditEntry> entries);

    /// <summary>
    /// Calculates audit coverage percentage.
    /// </summary>
    /// <param name="entries">Audit entries.</param>
    /// <param name="requiredActions">Actions that should be audited.</param>
    /// <returns>Percentage of required actions that have audit entries.</returns>
    public static double AuditCoverage(
        IEnumerable<AuditEntry> entries,
        IReadOnlyList<string> requiredActions);

    /// <summary>
    /// Detects gaps in audit logging (periods with no entries).
    /// </summary>
    /// <param name="entries">Audit entries.</param>
    /// <param name="maxGapSeconds">Maximum allowed gap before flagging.</param>
    /// <returns>List of gap periods as (start, end) tuples.</returns>
    public static IReadOnlyList<(long Start, long End)> DetectGaps(
        IReadOnlyList<AuditEntry> entries,
        long maxGapSeconds);

    /// <summary>
    /// Generates a compliance summary report.
    /// </summary>
    /// <param name="results">Compliance check results.</param>
    /// <returns>Summary with total/passed/failed counts and overall status.</returns>
    public static ComplianceSummary GenerateSummary(
        IReadOnlyList<ComplianceResult> results);
}

/// <summary>
/// Summary of compliance status.
/// </summary>
/// <param name="TotalRules">Number of rules checked.</param>
/// <param name="PassedRules">Number of rules passed.</param>
/// <param name="FailedRules">Number of rules failed.</param>
/// <param name="OverallCompliant">True if all rules passed.</param>
/// <param name="CompliancePercentage">Percentage of rules passed.</param>
public record ComplianceSummary(
    int TotalRules,
    int PassedRules,
    int FailedRules,
    bool OverallCompliant,
    double CompliancePercentage);

/// <summary>
/// Thread-safe audit log with hash chain integrity.
/// </summary>
public sealed class AuditLog
{
    /// <summary>
    /// Creates a new audit log.
    /// </summary>
    public AuditLog();

    /// <summary>
    /// Appends an entry to the audit log.
    /// </summary>
    /// <param name="entry">The entry to append.</param>
    /// <returns>The hash of the appended entry.</returns>
    public string Append(AuditEntry entry);

    /// <summary>
    /// Retrieves all entries.
    /// </summary>
    /// <returns>All audit entries with their hashes.</returns>
    public IReadOnlyList<(AuditEntry Entry, string Hash)> GetAll();

    /// <summary>
    /// Verifies the integrity of the entire log.
    /// </summary>
    /// <returns>True if log is intact.</returns>
    public bool VerifyIntegrity();

    /// <summary>
    /// Gets the number of entries.
    /// </summary>
    public int Count { get; }

    /// <summary>
    /// Gets the hash of the last entry (for chaining).
    /// </summary>
    public string? LastHash { get; }
}
```

### Required Classes/Records

| Type | Purpose |
|------|---------|
| `AuditEntry` | Immutable record for audit log entries |
| `ComplianceRule` | Definition of compliance requirements |
| `ComplianceResult` | Result of compliance validation |
| `ComplianceSummary` | Aggregated compliance status |
| `ComplianceAudit` | Static utility class for audit operations |
| `AuditLog` | Thread-safe append-only log with hash chain |

### Architectural Patterns to Follow

1. **Hash chain integrity** - Use `Security.Digest()` and `Security.HashChain()` for tamper detection
2. **Immutable records** - All data types are records for thread safety
3. **Static utility class** - Stateless operations in `ComplianceAudit`
4. **Thread-safe state** - `AuditLog` uses locking like `TokenStore`
5. **Deterministic iteration** - Sort by timestamp for reproducible results

### Acceptance Criteria

1. **Unit Tests**: Create `tests/StrataGuard.Tests/ComplianceTests.cs` with at least 15 test methods covering:
   - Hash chain building and verification
   - Tampering detection (modified entry breaks chain)
   - Compliance rule validation
   - Time range filtering
   - Actor grouping
   - Privileged action detection
   - Gap detection
   - Summary generation
   - Edge cases

2. **Integration Points**:
   - Use `Security.Digest()` for hashing
   - Use `Security.RequiresAudit()` to identify critical actions
   - Compatible with `Policy.PolicyAuditRequired()` for policy change tracking
   - Integrate with `WorkflowEngine.AuditLog` for workflow transitions

3. **Code Coverage**: Minimum 80% line coverage for new code

4. **Test Command**:
   ```bash
   dotnet test --filter "FullyQualifiedName~ComplianceTests"
   ```

---

## Task 3: Security Policy Evaluator

### Overview

Implement a security policy evaluation engine that defines, evaluates, and enforces security policies based on context, roles, and conditions. The service must integrate with `Security`, `Policy`, and the access control system.

### Interface Contract

```csharp
namespace StrataGuard;

/// <summary>
/// Represents a security policy definition.
/// </summary>
/// <param name="Id">Unique policy identifier.</param>
/// <param name="Name">Human-readable policy name.</param>
/// <param name="Effect">Allow or Deny.</param>
/// <param name="Actions">Actions this policy applies to.</param>
/// <param name="Resources">Resources this policy applies to (wildcards supported).</param>
/// <param name="Conditions">Optional conditions for policy activation.</param>
/// <param name="Priority">Higher priority policies are evaluated first.</param>
public record SecurityPolicy(
    string Id,
    string Name,
    PolicyEffect Effect,
    IReadOnlyList<string> Actions,
    IReadOnlyList<string> Resources,
    IReadOnlyList<PolicyCondition> Conditions,
    int Priority);

/// <summary>
/// Policy effect enumeration.
/// </summary>
public enum PolicyEffect
{
    Allow,
    Deny
}

/// <summary>
/// Condition that must be met for policy to apply.
/// </summary>
/// <param name="Attribute">Attribute to check (e.g., "time", "ip", "role").</param>
/// <param name="Operator">Comparison operator.</param>
/// <param name="Value">Value to compare against.</param>
public record PolicyCondition(string Attribute, ConditionOperator Operator, string Value);

/// <summary>
/// Condition operators.
/// </summary>
public enum ConditionOperator
{
    Equals,
    NotEquals,
    Contains,
    StartsWith,
    GreaterThan,
    LessThan,
    In
}

/// <summary>
/// Context for policy evaluation.
/// </summary>
/// <param name="Actor">User or service requesting access.</param>
/// <param name="Role">Role of the actor.</param>
/// <param name="Action">Action being attempted.</param>
/// <param name="Resource">Resource being accessed.</param>
/// <param name="Attributes">Additional context attributes.</param>
public record EvaluationContext(
    string Actor,
    string Role,
    string Action,
    string Resource,
    IReadOnlyDictionary<string, string> Attributes);

/// <summary>
/// Result of policy evaluation.
/// </summary>
/// <param name="Decision">Allow, Deny, or NotApplicable.</param>
/// <param name="MatchedPolicy">The policy that determined the decision.</param>
/// <param name="Reason">Explanation for the decision.</param>
public record EvaluationResult(
    PolicyDecision Decision,
    SecurityPolicy? MatchedPolicy,
    string Reason);

/// <summary>
/// Policy decision types.
/// </summary>
public enum PolicyDecision
{
    Allow,
    Deny,
    NotApplicable
}

/// <summary>
/// Static utility methods for policy evaluation.
/// </summary>
public static class PolicyEvaluator
{
    /// <summary>
    /// Evaluates a single policy against a context.
    /// </summary>
    /// <param name="policy">The policy to evaluate.</param>
    /// <param name="context">The evaluation context.</param>
    /// <returns>True if the policy matches the context.</returns>
    public static bool PolicyMatches(SecurityPolicy policy, EvaluationContext context);

    /// <summary>
    /// Evaluates a condition against context attributes.
    /// </summary>
    /// <param name="condition">The condition to evaluate.</param>
    /// <param name="attributes">Context attributes.</param>
    /// <returns>True if condition is satisfied.</returns>
    public static bool EvaluateCondition(
        PolicyCondition condition,
        IReadOnlyDictionary<string, string> attributes);

    /// <summary>
    /// Evaluates all policies and returns the final decision.
    /// Uses first-match semantics with priority ordering.
    /// </summary>
    /// <param name="policies">All policies to consider.</param>
    /// <param name="context">The evaluation context.</param>
    /// <returns>The evaluation result.</returns>
    public static EvaluationResult Evaluate(
        IReadOnlyList<SecurityPolicy> policies,
        EvaluationContext context);

    /// <summary>
    /// Checks if a resource pattern matches a specific resource.
    /// Supports wildcards: "*" matches any single segment, "**" matches any path.
    /// </summary>
    /// <param name="pattern">Resource pattern (e.g., "/api/users/*").</param>
    /// <param name="resource">Actual resource path.</param>
    /// <returns>True if pattern matches resource.</returns>
    public static bool ResourceMatches(string pattern, string resource);

    /// <summary>
    /// Validates a policy for consistency and correctness.
    /// </summary>
    /// <param name="policy">Policy to validate.</param>
    /// <returns>Null if valid, error message if invalid.</returns>
    public static string? ValidatePolicy(SecurityPolicy policy);

    /// <summary>
    /// Finds conflicting policies (same action/resource but different effects).
    /// </summary>
    /// <param name="policies">Policies to analyze.</param>
    /// <returns>List of conflicting policy pairs.</returns>
    public static IReadOnlyList<(SecurityPolicy A, SecurityPolicy B)> FindConflicts(
        IReadOnlyList<SecurityPolicy> policies);

    /// <summary>
    /// Calculates the effective permissions for a role across all policies.
    /// </summary>
    /// <param name="policies">All policies.</param>
    /// <param name="role">Role to analyze.</param>
    /// <returns>Dictionary of resource patterns to allowed actions.</returns>
    public static IReadOnlyDictionary<string, IReadOnlyList<string>> EffectivePermissions(
        IReadOnlyList<SecurityPolicy> policies,
        string role);

    /// <summary>
    /// Simulates policy evaluation for testing/auditing.
    /// </summary>
    /// <param name="policies">Policies to test.</param>
    /// <param name="contexts">Test contexts.</param>
    /// <returns>Results for each context.</returns>
    public static IReadOnlyList<(EvaluationContext Context, EvaluationResult Result)> SimulateBatch(
        IReadOnlyList<SecurityPolicy> policies,
        IReadOnlyList<EvaluationContext> contexts);
}

/// <summary>
/// Thread-safe policy registry with versioning.
/// </summary>
public sealed class PolicyRegistry
{
    /// <summary>
    /// Creates a new policy registry.
    /// </summary>
    public PolicyRegistry();

    /// <summary>
    /// Registers a new policy or updates an existing one.
    /// </summary>
    /// <param name="policy">The policy to register.</param>
    /// <returns>The new version number.</returns>
    public int Register(SecurityPolicy policy);

    /// <summary>
    /// Removes a policy by ID.
    /// </summary>
    /// <param name="policyId">The policy ID to remove.</param>
    /// <returns>True if removed, false if not found.</returns>
    public bool Remove(string policyId);

    /// <summary>
    /// Gets a policy by ID.
    /// </summary>
    /// <param name="policyId">The policy ID.</param>
    /// <returns>The policy, or null if not found.</returns>
    public SecurityPolicy? Get(string policyId);

    /// <summary>
    /// Gets all policies ordered by priority (descending).
    /// </summary>
    /// <returns>All registered policies.</returns>
    public IReadOnlyList<SecurityPolicy> GetAll();

    /// <summary>
    /// Evaluates policies against a context.
    /// </summary>
    /// <param name="context">The evaluation context.</param>
    /// <returns>The evaluation result.</returns>
    public EvaluationResult Evaluate(EvaluationContext context);

    /// <summary>
    /// Gets the current version number.
    /// </summary>
    public int Version { get; }

    /// <summary>
    /// Gets the number of registered policies.
    /// </summary>
    public int Count { get; }
}
```

### Required Classes/Records

| Type | Purpose |
|------|---------|
| `SecurityPolicy` | Policy definition with actions, resources, conditions |
| `PolicyEffect` | Allow/Deny enumeration |
| `PolicyCondition` | Condition for conditional policies |
| `ConditionOperator` | Comparison operators for conditions |
| `EvaluationContext` | Request context for policy evaluation |
| `EvaluationResult` | Result of policy evaluation |
| `PolicyDecision` | Allow/Deny/NotApplicable decision |
| `PolicyEvaluator` | Static utility class for evaluation logic |
| `PolicyRegistry` | Thread-safe policy storage and evaluation |

### Architectural Patterns to Follow

1. **Enum types** - Use enums for discrete values (like `CircuitBreakerState` constants)
2. **Wildcard matching** - Implement resource pattern matching for flexible policies
3. **Priority-based evaluation** - Higher priority policies evaluated first
4. **Thread-safe registry** - Follow `RouteTable`, `CheckpointManager` patterns
5. **Validation methods** - Return `string?` for validation (null = valid)
6. **Deterministic ordering** - Sort by priority, then by ID for stable results

### Acceptance Criteria

1. **Unit Tests**: Create `tests/StrataGuard.Tests/PolicyEvaluatorTests.cs` with at least 18 test methods covering:
   - Basic policy matching (action, resource)
   - Wildcard resource patterns ("*", "**")
   - Condition evaluation (all operators)
   - Priority-based evaluation (higher priority wins)
   - Allow/Deny semantics
   - Policy validation
   - Conflict detection
   - Effective permissions calculation
   - Batch simulation
   - Registry operations (CRUD, versioning)
   - Edge cases

2. **Integration Points**:
   - Use `Security.AccessLevel()` for role-based access level comparison
   - Integrate with `Policy.PolicyAuditRequired()` for audit decisions
   - Compatible with existing policy state machine (`Policy.NextPolicy`, etc.)

3. **Code Coverage**: Minimum 80% line coverage for new code

4. **Test Command**:
   ```bash
   dotnet test --filter "FullyQualifiedName~PolicyEvaluatorTests"
   ```

---

## General Guidelines

### File Organization

Place new source files in `src/StrataGuard/`:
- `IntrusionDetection.cs` - Task 1
- `ComplianceAudit.cs` - Task 2
- `PolicyEvaluator.cs` - Task 3

Place test files in `tests/StrataGuard.Tests/`:
- `IntrusionTests.cs` - Task 1
- `ComplianceTests.cs` - Task 2
- `PolicyEvaluatorTests.cs` - Task 3

### Code Style

Follow existing patterns in the codebase:
- Use file-scoped namespaces: `namespace StrataGuard;`
- Use collection expressions: `[]` instead of `new List<T>()`
- Use target-typed `new`: `new()` when type is clear
- Use pattern matching in switch expressions
- Lock objects should be named `_lock`
- Use `IReadOnlyList<T>` and `IReadOnlyDictionary<K,V>` for return types

### Testing Pattern

Follow the existing test patterns:
```csharp
using Xunit;

namespace StrataGuard.Tests;

public class ExampleTests
{
    [Fact]
    public void MethodName_Scenario_ExpectedResult()
    {
        // Arrange
        // Act
        // Assert
    }

    [Theory]
    [InlineData(input1, expected1)]
    [InlineData(input2, expected2)]
    public void MethodName_ParameterizedTest(int input, int expected)
    {
        // Test with multiple inputs
    }
}
```

### Running All Tests

```bash
dotnet test --verbosity normal
```

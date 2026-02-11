# StrataGuard - Greenfield Tasks

## Overview

StrataGuard provides 3 greenfield implementation tasks that require building new security and operational modules from scratch. These tasks test your ability to design clean APIs, integrate with existing systems, implement thread-safe data structures, and write comprehensive test suites following established codebase patterns.

## Environment

- **Language**: C# (.NET 8.0)
- **Infrastructure**: xUnit test framework, Docker-based deployment
- **Difficulty**: Apex-Principal

## Tasks

### Task 1: Intrusion Detection Service (Greenfield Implementation)

Implement a comprehensive intrusion detection service that monitors system events, identifies suspicious patterns against configurable detection rules, and raises security alerts. Design immutable records for IntrusionEvent and DetectionRule, implement a thread-safe IntrusionStore with retention-based cleanup, and create a static IntrusionDetection utility class with analysis methods for threat scoring, blocking decisions, attack rate calculation, signature grouping, and coordinated attack detection. Must integrate with Security.Digest() for event hashing and Severity constants for threat levels.

**Key Interfaces**:
- `IntrusionEvent` - Detected intrusion record with IP, service, threat level, signature
- `DetectionRule` - Pattern-based detection rule with threat classification
- `IntrusionStore` - Thread-safe event storage with time-based retention and cleanup
- `IntrusionDetection` - Static utility class with Analyze(), ThreatScore(), ShouldBlock(), GroupBySignature(), AttackRate(), TopTargets(), and CorrelateAttacks() methods

### Task 2: Compliance Audit Logger (Greenfield Implementation)

Design and implement a compliance audit logging service that records security-relevant actions, generates audit reports, and validates compliance with security policies. Build immutable records for AuditEntry, ComplianceRule, and ComplianceResult. Implement a tamper-evident hash chain using Security.Digest() for integrity verification. Create an append-only AuditLog with thread-safe operations and a static ComplianceAudit class with hash chain building, compliance validation, time-range filtering, actor grouping, privileged action detection, gap detection, and summary generation. Must support integration with Policy.PolicyAuditRequired() for audit decision tracking.

**Key Interfaces**:
- `AuditEntry` - Immutable record for auditable actions with actor, action, resource, outcome, metadata
- `ComplianceRule` - Policy requirement definition with required actions and retention periods
- `ComplianceResult` - Compliance check result with rule, status, and findings
- `ComplianceSummary` - Aggregated compliance status and percentage
- `AuditLog` - Thread-safe append-only log with hash chain integrity verification
- `ComplianceAudit` - Static utility class with BuildHashChain(), VerifyHashChain(), ValidateCompliance(), FilterByTimeRange(), GroupByActor(), FindPrivilegedActions(), DetectGaps(), and GenerateSummary() methods

### Task 3: Security Policy Evaluator (Greenfield Implementation)

Build a security policy evaluation engine that defines, evaluates, and enforces context-based security policies with wildcard resource matching and conditional logic. Design SecurityPolicy records with actions, resources, conditions, and priority levels. Implement PolicyEffect and PolicyDecision enums plus PolicyCondition records supporting multiple operators (Equals, NotEquals, Contains, StartsWith, GreaterThan, LessThan, In). Create a static PolicyEvaluator class with policy matching, condition evaluation, wildcard resource matching, policy validation, conflict detection, effective permission calculation, and batch simulation. Implement a thread-safe PolicyRegistry for policy storage and evaluation with versioning support.

**Key Interfaces**:
- `SecurityPolicy` - Policy definition with ID, name, effect, actions, resources, conditions, priority
- `PolicyEffect` - Allow/Deny enumeration
- `PolicyCondition` - Conditional rule with attribute, operator, value
- `ConditionOperator` - Comparison operators: Equals, NotEquals, Contains, StartsWith, GreaterThan, LessThan, In
- `EvaluationContext` - Request context with actor, role, action, resource, attributes
- `EvaluationResult` - Policy evaluation result with decision, matched policy, reason
- `PolicyDecision` - Allow/Deny/NotApplicable enumeration
- `PolicyRegistry` - Thread-safe policy storage with versioning and evaluation
- `PolicyEvaluator` - Static utility class with PolicyMatches(), EvaluateCondition(), Evaluate(), ResourceMatches(), ValidatePolicy(), FindConflicts(), EffectivePermissions(), and SimulateBatch() methods

## Getting Started

```bash
dotnet test --verbosity normal
```

## Success Criteria

Each greenfield task must meet all acceptance criteria defined in [TASKS_GREENFIELD.md](./TASKS_GREENFIELD.md), including:

- Complete implementation of all required classes and methods
- Minimum 80% line coverage with comprehensive test suites (15+ test methods per task)
- Proper integration with existing StrataGuard modules (Security, Policy, Workflow)
- Thread-safe concurrent access patterns
- Immutable record types and deterministic ordering for reproducible results
- Clean separation of concerns between static utilities and state-managing classes

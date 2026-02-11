# AegisCore - Greenfield Implementation Tasks

## Overview

AegisCore supports three greenfield implementation tasks that extend the security platform with new major subsystems: a real-time threat detection engine, an access log analyzer for anomaly detection, and a secret rotation service for credential management. These tasks require implementing complete modules from scratch while integrating with the existing codebase.

## Environment

- **Language**: C# 12 / .NET 8
- **Infrastructure**: Maritime dispatch reliability platform with eight interconnected services
- **Difficulty**: Hyper-Principal

## Tasks

### Task 1: Threat Detection Engine (Greenfield)

Implement a real-time threat detection engine that ingests security events, correlates related incidents using sliding windows, evaluates configurable detection rules, and computes threat scores for sources. Implement `IThreatDetector` interface with `Analyze()`, `RegisterRule()`, `RemoveRule()`, `GetRules()`, `GetRecentThreats()`, `CorrelateBySource()`, `ComputeThreatScore()`, and `PurgeExpiredEvents()` methods. Include `SecurityEvent`, `Threat`, and `DetectionRule` records with a static `ThreatClassifier` helper for threat categorization and action suggestions. Requires thread-safe event correlation with O(1) rule lookup, integration with `Policy` module for escalation decisions, and minimum 50 unit tests.

**Key Interfaces:**
```csharp
public record SecurityEvent(string Id, string Source, string EventType, long Timestamp, IReadOnlyDictionary<string, string> Payload);
public record Threat(string ThreatId, int Severity, string Category, IReadOnlyList<string> CorrelatedEvents, IReadOnlyList<string> RecommendedActions, long DetectedAt);
public interface IThreatDetector { ... }
```

### Task 2: Access Log Analyzer (Greenfield)

Implement an access log analyzer that tracks user sessions, detects anomalous access patterns, computes access statistics, and identifies security violations such as impossible travel or privilege escalation. Implement `IAccessLogAnalyzer` interface with `RecordAccess()`, `GetUserStats()`, `GetAnomalies()`, `GetUserLogs()`, `GetResourceLogs()`, `IsSessionCompromised()`, `GetTopResources()`, and `PurgeLogs()` methods. Include `AccessLogEntry`, `AccessAnomaly`, `UserAccessStats`, and `AnomalyConfig` records with a static `GeoAnalyzer` helper for Haversine distance calculations and impossible travel detection. Requires thread-safe implementation with efficient indexing by user and resource, minimum 50 unit tests, and optional integration with `ThreatDetector` (Task 1).

**Key Interfaces:**
```csharp
public record AccessLogEntry(string LogId, string UserId, string Resource, string Action, long Timestamp, string IpAddress, (double Lat, double Lon)? GeoLocation, bool Success);
public record AccessAnomaly(string AnomalyId, string UserId, string AnomalyType, int Severity, string Description, IReadOnlyList<string> RelatedLogs, long DetectedAt);
public interface IAccessLogAnalyzer { ... }
```

### Task 3: Secret Rotation Service (Greenfield)

Implement a secret rotation service that manages credentials, API keys, and certificates with automatic rotation schedules, TTL enforcement, audit logging, and integration with `TokenStore` and `Security` modules. Implement `ISecretRotationService` interface with `Register()`, `GetValue()`, `Rotate()`, `Revoke()`, `GetMetadata()`, `GetSecretsNeedingRotation()`, `GetExpiringSecrets()`, `Validate()`, `GetAuditLog()`, `GetAuditLogRange()`, `AutoRotate()`, and `GetSecretCountsByType()` methods. Include `ManagedSecret`, `RotationResult`, `SecretAuditEntry`, and `RotationConfig` records with a static `SecretHelpers` class for cryptographic generation and validation. Requires thread-safe implementation with constant-time comparison using `CryptographicOperations.FixedTimeEquals`, complete audit trails, and minimum 60 unit tests with zero secret values in logs.

**Key Interfaces:**
```csharp
public enum SecretType { ApiKey, DatabaseCredential, Certificate, EncryptionKey, ServiceToken }
public record ManagedSecret(string SecretId, string Name, SecretType Type, long CreatedAt, long ExpiresAt, long RotationIntervalSeconds, long LastRotatedAt, int Version, bool IsActive);
public interface ISecretRotationService { ... }
```

## Getting Started

```bash
cd csharp/aegiscore && dotnet test
```

## Success Criteria

Implementation meets the acceptance criteria and interface contracts defined in [TASKS_GREENFIELD.md](./TASKS_GREENFIELD.md). Choose one or more tasks to implement. Each task requires thread-safe implementations following existing patterns (e.g., `TokenStore`, `WorkflowEngine`), comprehensive test coverage with minimum 50-60 unit tests per task, and integration points with existing modules where applicable. Study existing modules like `Resilience.cs`, `Security.cs`, and `Workflow.cs` for architectural guidance on thread safety, record usage, and XML documentation standards.

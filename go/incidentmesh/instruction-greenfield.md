# IncidentMesh - Greenfield Tasks

## Overview

IncidentMesh presents 3 greenfield tasks requiring implementation of complete new modules from scratch within the incident management platform. Each task defines a complete interface contract, required types, and acceptance criteria. Implementations must follow existing architectural patterns found in `internal/` and `services/`.

## Environment

- **Language**: Go 1.21+
- **Infrastructure**: Global emergency response coordination platform with 13 microservices and 10 internal packages
- **Difficulty**: Ultra-Principal

## Tasks

### Task 1: Postmortem Generator

Implement a **Postmortem Generator** module that analyzes resolved incidents and produces structured postmortem reports. This service aggregates incident timelines, identifies contributing factors, calculates response metrics, and generates actionable improvement recommendations. Locations: `internal/postmortem/generator.go` and `services/postmortem/service.go`.

**Core Interfaces:**
- `Generator` interface with methods: `GenerateReport()`, `BuildTimeline()`, `CalculateMetrics()`, `IdentifyRootCauses()`, `GenerateActionItems()`, `ValidateReport()`, `SeverityFromMetrics()`, `SummarizeBatch()`
- Types: `PostmortemReport`, `TimelineEntry`, `ImpactMetrics`, `ActionItem`, `BatchSummary`, `RootCauseStat`

**Integration Points:** `models.Incident`, `contracts.IncidentEvent`, `contracts.AuditEntry`, `internal/compliance`, `internal/events`

### Task 2: Alert Grouping Service

Implement an **Alert Grouping Service** that intelligently clusters related alerts to reduce alert fatigue and improve incident correlation. Groups alerts based on temporal proximity, region, severity patterns, and content similarity. Locations: `internal/alerting/grouper.go` and `services/alerting/service.go`.

**Core Interfaces:**
- `Grouper` interface with methods: `GroupAlerts()`, `FindGroup()`, `MergeGroups()`, `EvaluateRule()`, `DeduplicateAlerts()`, `SeverityRollup()`, `ExpireGroups()`, `SplitGroup()`, `LinkToIncident()`, `GroupStatistics()`
- `LabelMatcher` interface for similarity scoring
- Types: `Alert`, `AlertGroup`, `GroupingRule`, `GroupingConfig`, `GroupStats`

**Integration Points:** `internal/triage`, `services/escalation`, `internal/events`

### Task 3: On-Call Schedule Manager

Implement an **On-Call Schedule Manager** that handles responder rotations, overrides, escalation chains, and availability tracking. Supports multiple schedule layers, holiday handling, and timezone-aware scheduling. Locations: `internal/oncall/scheduler.go` and `services/oncall/service.go`.

**Core Interfaces:**
- `Scheduler` interface with methods: `ResolveOnCall()`, `GetShifts()`, `CreateOverride()`, `ValidateOverride()`, `CalculateRotation()`, `NextHandoff()`, `FindCoverage()`, `EscalationChain()`, `CheckAvailability()`, `RotationGaps()`, `ScheduleStatistics()`
- Types: `Responder`, `Schedule`, `ScheduleLayer`, `Override`, `EscalationStep`, `OnCallShift`, `EscalationContact`, `TimeGap`, `ScheduleStats`

**Integration Points:** `internal/escalation`, `services/notifications`, `contracts.IncidentEvent`

## Getting Started

```bash
# Run all tests (verbose, race detector)
go test -race -v ./...

# Verify with Harbor
bash harbor/test.sh
```

## Success Criteria

Each task requires:
1. Minimum 15-25 unit tests with edge case coverage
2. 5+ integration tests per module
3. >= 80% line coverage for `internal/` packages
4. Integration with specified existing modules
5. All acceptance criteria from [TASKS_GREENFIELD.md](./TASKS_GREENFIELD.md) satisfied

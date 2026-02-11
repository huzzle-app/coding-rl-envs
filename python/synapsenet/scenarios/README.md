# SynapseNet Debugging Scenarios

This directory contains realistic debugging scenarios that simulate real-world incidents, tickets, and alerts that an engineer might encounter while operating SynapseNet.

## Purpose

These scenarios describe **symptoms**, not solutions. They are designed to:
- Simulate realistic production incidents
- Test debugging skills across the ML platform stack
- Require investigation across multiple services and components
- Match the types of issues described in TASK.md

## Scenarios

| File | Type | Domain | Services Involved |
|------|------|--------|-------------------|
| `01_model_memory_crisis.md` | PagerDuty Incident | Model Serving | inference, registry, storage |
| `02_training_reproducibility.md` | Slack Discussion | Distributed Training | training, experiments, workers |
| `03_feature_drift_storm.md` | Alert Flood | Feature Store | features, monitoring, pipeline |
| `04_ab_test_disaster.md` | Jira Ticket | Model Serving | inference, experiments, gateway |
| `05_distributed_training_hang.md` | Incident Report | Distributed Training | training, workers, registry |

## How to Use

1. Read a scenario to understand the reported symptoms
2. Use the symptoms to guide your investigation
3. Look for related bugs in the codebase that could cause these symptoms
4. Note that each scenario may involve multiple related bugs

## Scenario Format

Each scenario includes:
- **Context**: When and how the issue was discovered
- **Symptoms**: Observable behavior that something is wrong
- **Impact**: Business or user impact
- **Investigation notes**: What has been tried (may include red herrings)
- **Timeline**: When events occurred

## Mapping to Bug Categories

These scenarios map to the bug categories in TASK.md:
- Model Serving (B1-B9, H1, H6, H8)
- Distributed Training (A1-A9, F10)
- ML Pipeline (M1-M9)
- Feature Store (C1-C8)
- Experiment Tracking (E1-E8)
- Observability (J1-J6)

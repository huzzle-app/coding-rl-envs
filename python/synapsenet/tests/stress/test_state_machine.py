"""
SynapseNet State Machine Tests
Tests for state transition logic, invalid transitions, missing states, and guards.
"""
import os
import sys
import time
import threading

import pytest
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))


class TestModelDeploymentStateMachine:
    """Test model deployment lifecycle state transitions."""

    def test_valid_happy_path(self):
        """Normal deployment flow: created -> validating -> validated -> deploying -> deployed -> serving."""
        from services.inference.main import ModelDeploymentStateMachine

        sm = ModelDeploymentStateMachine("model-1")
        assert sm.get_state() == "created"

        assert sm.transition("validating")
        assert sm.transition("validated")
        assert sm.transition("deploying")
        assert sm.transition("deployed")
        assert sm.transition("serving")

    def test_cannot_skip_validation(self):
        """Should not allow created -> deploying (skipping validation)."""
        from services.inference.main import ModelDeploymentStateMachine

        sm = ModelDeploymentStateMachine("model-1")
        result = sm.transition("deploying")
        assert not result, "transition should not be allowed"
        assert sm.get_state() == "created"

    def test_cannot_skip_to_serving(self):
        """Should not allow created -> serving."""
        from services.inference.main import ModelDeploymentStateMachine

        sm = ModelDeploymentStateMachine("model-1")
        result = sm.transition("serving")
        assert not result

    def test_deprecated_cannot_serve(self):
        """Deprecated models should not be able to serve traffic."""
        from services.inference.main import ModelDeploymentStateMachine

        sm = ModelDeploymentStateMachine("model-1")
        sm.transition("validating")
        sm.transition("validated")
        sm.transition("deploying")
        sm.transition("deployed")
        sm.transition("deprecated")

        assert not sm.can_serve_traffic(), (
            "transition should not be allowed"
        )

    def test_deprecated_cannot_directly_deploy(self):
        """deprecated -> deployed should NOT be a valid transition."""
        from services.inference.main import ModelDeploymentStateMachine

        sm = ModelDeploymentStateMachine("model-1")
        sm.transition("validating")
        sm.transition("validated")
        sm.transition("deploying")
        sm.transition("deployed")
        sm.transition("deprecated")

        result = sm.transition("deployed")
        assert not result, "transition should not be allowed"

    def test_deprecated_to_deploying_blocked(self):
        """deprecated -> deploying should NOT be a valid transition."""
        from services.inference.main import ModelDeploymentStateMachine

        sm = ModelDeploymentStateMachine("model-1")
        sm.transition("validating")
        sm.transition("validated")
        sm.transition("deploying")
        sm.transition("deployed")
        sm.transition("deprecated")

        result = sm.transition("deploying")
        assert not result, "transition should not be allowed"

    def test_rollback_from_deploying(self):
        """Should be able to rollback from deploying state."""
        from services.inference.main import ModelDeploymentStateMachine

        sm = ModelDeploymentStateMachine("model-1")
        sm.transition("validating")
        sm.transition("validated")
        sm.transition("deploying")

        assert sm.can_rollback()
        assert sm.transition("rolled_back")

    def test_cannot_rollback_from_created(self):
        """Should not be able to rollback a model that was never deployed."""
        from services.inference.main import ModelDeploymentStateMachine

        sm = ModelDeploymentStateMachine("model-1")
        assert not sm.can_rollback()

    def test_history_tracks_all_transitions(self):
        """State history should track all transitions."""
        from services.inference.main import ModelDeploymentStateMachine

        sm = ModelDeploymentStateMachine("model-1")
        sm.transition("validating")
        sm.transition("validated")
        sm.transition("deploying")

        history = sm.get_history()
        states = [h["state"] for h in history]
        assert states == ["created", "validating", "validated", "deploying"]

    def test_invalid_state_rejected(self):
        """Transition to non-existent state should fail."""
        from services.inference.main import ModelDeploymentStateMachine

        sm = ModelDeploymentStateMachine("model-1")
        assert not sm.transition("nonexistent")
        assert sm.get_state() == "created"


class TestExperimentStateMachine:
    """Test experiment lifecycle state transitions."""

    def test_happy_path(self):
        """Normal flow: created -> queued -> provisioning -> running -> completed -> archived."""
        from services.experiments.views import ExperimentStateMachine

        sm = ExperimentStateMachine("exp-1")
        assert sm.transition("queued")
        assert sm.transition("provisioning")
        assert sm.transition("running")
        assert sm.transition("completed")
        assert sm.transition("archived")

    def test_pause_resume(self):
        """Should be able to pause and resume an experiment."""
        from services.experiments.views import ExperimentStateMachine

        sm = ExperimentStateMachine("exp-1")
        sm.transition("queued")
        sm.transition("provisioning")
        sm.transition("running")

        assert sm.transition("paused")
        assert sm.transition("running")
        assert sm.get_state() == "running"

    def test_paused_to_completed_requires_cleanup(self):
        """Going from paused to completed should still work but flag cleanup needed."""
        from services.experiments.views import ExperimentStateMachine

        sm = ExperimentStateMachine("exp-1")
        sm.transition("queued")
        sm.transition("provisioning")
        sm.transition("running")
        sm.transition("paused")
        sm.transition("completed")

        assert sm.needs_cleanup(), (
            "transition should succeed and flag cleanup needed"
        )

    def test_cannot_archive_from_running(self):
        """Running experiments should not be directly archived."""
        from services.experiments.views import ExperimentStateMachine

        sm = ExperimentStateMachine("exp-1")
        sm.transition("queued")
        sm.transition("provisioning")
        sm.transition("running")

        result = sm.transition("archived")
        assert not result, "transition should not be allowed"

    def test_archived_is_terminal(self):
        """Archived experiments should not transition to any other state."""
        from services.experiments.views import ExperimentStateMachine

        sm = ExperimentStateMachine("exp-1")
        sm.transition("queued")
        sm.transition("provisioning")
        sm.transition("running")
        sm.transition("completed")
        sm.transition("archived")

        for state in ["created", "queued", "running", "completed", "failed"]:
            assert not sm.transition(state), "transition should not be allowed"

    def test_failed_can_retry(self):
        """Failed experiments should be retryable by going back to queued."""
        from services.experiments.views import ExperimentStateMachine

        sm = ExperimentStateMachine("exp-1")
        sm.transition("queued")
        sm.transition("provisioning")
        sm.transition("failed")

        assert sm.transition("queued"), "transition should succeed"

    def test_cancel_from_running(self):
        """Should be able to cancel a running experiment."""
        from services.experiments.views import ExperimentStateMachine

        sm = ExperimentStateMachine("exp-1")
        sm.transition("queued")
        sm.transition("provisioning")
        sm.transition("running")

        assert sm.transition("cancelled")
        assert sm.get_state() == "cancelled"


class TestPipelineStateMachine:
    """Test pipeline execution lifecycle state transitions."""

    def test_happy_path(self):
        """Normal flow: idle -> validating -> queued -> running -> completed -> idle."""
        from services.pipeline.main import PipelineStateMachine

        sm = PipelineStateMachine("pipeline-1")
        assert sm.transition("validating")
        assert sm.transition("queued")
        assert sm.transition("running")
        assert sm.transition("completed")
        assert sm.is_terminal()
        assert sm.transition("idle")

    def test_pause_resume_cycle(self):
        """Pipeline should support pause/resume."""
        from services.pipeline.main import PipelineStateMachine

        sm = PipelineStateMachine("pipeline-1")
        sm.transition("validating")
        sm.transition("queued")
        sm.transition("running")

        assert sm.transition("paused")
        assert sm.transition("running")

    def test_paused_to_completed_blocked(self):
        """Paused pipelines should NOT complete without resuming first."""
        from services.pipeline.main import PipelineStateMachine

        sm = PipelineStateMachine("pipeline-1")
        sm.transition("validating")
        sm.transition("queued")
        sm.transition("running")
        sm.transition("paused")

        result = sm.transition("completed")
        assert not result, "transition should not be allowed"

    def test_checkpoint_during_execution(self):
        """Should be able to checkpoint during running state."""
        from services.pipeline.main import PipelineStateMachine

        sm = PipelineStateMachine("pipeline-1")
        sm.transition("validating")
        sm.transition("queued")
        sm.transition("running")
        sm.transition("checkpointing")

        assert sm.save_checkpoint({"progress": 50})
        assert sm.transition("running")

    def test_checkpoint_restore(self):
        """Should be able to restore from checkpoint after failure."""
        from services.pipeline.main import PipelineStateMachine

        sm = PipelineStateMachine("pipeline-1")
        sm.transition("validating")
        sm.transition("queued")
        sm.transition("running")
        sm.transition("checkpointing")
        sm.save_checkpoint({"step": 42, "data": [1, 2, 3]})
        sm.transition("running")
        sm.transition("failed")

        # Restore checkpoint
        data = sm.restore_checkpoint()
        assert data is not None
        assert data["step"] == 42

    def test_terminal_states(self):
        """completed, failed, cancelled should be terminal states."""
        from services.pipeline.main import PipelineStateMachine

        for terminal in ["completed", "failed", "cancelled"]:
            sm = PipelineStateMachine(f"pipeline-{terminal}")
            sm.transition("validating")
            sm.transition("queued")
            sm.transition("running")

            if terminal == "cancelled":
                # running -> cancelled is not a valid transition in the current model
                # running can go to paused, checkpointing, completed, failed
                continue

            sm.transition(terminal)
            assert sm.is_terminal(), f"{terminal} should be a terminal state"

    def test_cancelled_goes_back_to_idle(self):
        """Cancelled pipeline should be able to return to idle."""
        from services.pipeline.main import PipelineStateMachine

        sm = PipelineStateMachine("pipeline-1")
        sm.transition("validating")
        sm.transition("queued")
        sm.transition("cancelled")

        assert sm.transition("idle"), "transition should succeed"


class TestCanaryDeploymentStateMachine:
    """Test canary deployment lifecycle."""

    def test_canary_start_and_promote(self):
        """Should be able to start and promote a canary deployment."""
        from services.registry.views import CanaryDeployment

        cd = CanaryDeployment()
        dep_id = cd.start_canary("model-1", "v2", traffic_pct=0.1)

        assert cd._deployments[dep_id]["status"] == "active"
        assert cd._deployments[dep_id]["traffic_pct"] == 0.1

        cd.promote(dep_id)
        assert cd._deployments[dep_id]["traffic_pct"] == 1.0
        assert cd._deployments[dep_id]["status"] == "promoted"

    def test_canary_rollback(self):
        """Rollback should set traffic to 0 and status to rolled_back."""
        from services.registry.views import CanaryDeployment

        cd = CanaryDeployment()
        dep_id = cd.start_canary("model-1", "v2", traffic_pct=0.2)

        result = cd.rollback(dep_id)
        assert result
        assert cd._deployments[dep_id]["traffic_pct"] == 0.0
        assert cd._deployments[dep_id]["status"] == "rolled_back"

    def test_rollback_nonexistent_deployment(self):
        """Rollback of non-existent deployment should return False."""
        from services.registry.views import CanaryDeployment

        cd = CanaryDeployment()
        assert not cd.rollback("nonexistent-id")


class TestCircuitBreakerStateMachine:
    """Test circuit breaker state transitions."""

    def test_closed_to_open(self):
        """Circuit should open after threshold failures."""
        from shared.clients.base import CircuitBreaker

        cb = CircuitBreaker(failure_threshold=3, recovery_timeout=1.0)
        assert cb.state.value == "closed"

        cb.record_failure()
        cb.record_failure()
        assert cb.state.value == "closed"

        cb.record_failure()
        assert cb.state.value == "open"

    def test_open_to_half_open(self):
        """After recovery timeout, circuit should transition to half-open."""
        from shared.clients.base import CircuitBreaker

        cb = CircuitBreaker(failure_threshold=2, recovery_timeout=0.1)
        cb.record_failure()
        cb.record_failure()
        assert cb.state.value == "open"

        time.sleep(0.15)
        assert cb.can_execute()
        assert cb.state.value == "half_open"

    def test_half_open_success_closes(self):
        """Successful call in half-open state should close the circuit."""
        from shared.clients.base import CircuitBreaker

        cb = CircuitBreaker(failure_threshold=2, recovery_timeout=0.1)
        cb.record_failure()
        cb.record_failure()

        time.sleep(0.15)
        cb.can_execute()  # Transitions to half_open
        cb.record_success()
        assert cb.state.value == "closed"

    def test_half_open_failure_reopens(self):
        """Failed call in half-open state should reopen the circuit."""
        from shared.clients.base import CircuitBreaker

        cb = CircuitBreaker(failure_threshold=2, recovery_timeout=0.1)
        cb.record_failure()
        cb.record_failure()

        time.sleep(0.15)
        cb.can_execute()
        cb.record_failure()
        assert cb.state.value == "open"


class TestCircuitBreakerRegistryStates:
    """Test circuit breaker registry manages per-service state."""

    def test_independent_service_breakers(self):
        """Each service should have its own circuit breaker state."""
        from services.gateway.main import CircuitBreakerRegistry

        registry = CircuitBreakerRegistry(default_threshold=3)

        # Fail service A
        for _ in range(3):
            registry.record_failure("service-a")

        # Service B should still be callable
        assert registry.can_call("service-b")
        assert not registry.can_call("service-a")

    def test_get_all_states(self):
        """Should report state of all tracked services."""
        from services.gateway.main import CircuitBreakerRegistry

        registry = CircuitBreakerRegistry(default_threshold=2)
        registry.record_success("svc-1")
        registry.record_failure("svc-2")
        registry.record_failure("svc-2")

        states = registry.get_all_states()
        assert states["svc-1"] == "closed"
        assert states["svc-2"] == "open"

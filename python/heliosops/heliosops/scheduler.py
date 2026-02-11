"""
HeliosOps Scheduler Module
===========================

Task scheduling, SLA deadline tracking, and periodic task execution for
the emergency dispatch platform.  Provides both synchronous utilities and
async-compatible scheduling primitives.
"""
from __future__ import annotations

import asyncio
import copy
import logging
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Coroutine, Dict, List, Optional

from .models import Incident, IncidentStatus

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Task scheduling
# ---------------------------------------------------------------------------

class ScheduledTask:
    """A delayed task that fires at a specified time."""

    def __init__(
        self,
        task_id: str,
        callback: Callable[..., Any],
        fire_at: datetime,
        args: tuple = (),
        kwargs: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.task_id = task_id
        self.callback = callback
        self.fire_at = fire_at
        self.args = args
        self.kwargs = kwargs or {}
        self.executed = False
        self.result: Any = None

    def is_due(self, now: Optional[datetime] = None) -> bool:
        """Check whether the task should fire.

        """
        
        
        # Fixing schedule_task() to use datetime.now(timezone.utc) will reveal this:
        # TypeError on comparison between offset-naive and offset-aware datetimes
        check_time = now or datetime.now()
        return check_time >= self.fire_at

    def execute(self) -> Any:
        """Run the task callback."""
        if self.executed:
            return self.result
        self.result = self.callback(*self.args, **self.kwargs)
        self.executed = True
        return self.result


def schedule_task(
    task_id: str,
    callback: Callable[..., Any],
    delay_seconds: float,
    args: tuple = (),
    kwargs: Optional[Dict[str, Any]] = None,
) -> ScheduledTask:
    """Schedule a task to execute after a delay.

    """
    fire_at = datetime.now() + timedelta(seconds=delay_seconds)
    return ScheduledTask(
        task_id=task_id,
        callback=callback,
        fire_at=fire_at,
        args=args,
        kwargs=kwargs,
    )


# ---------------------------------------------------------------------------
# SLA deadline tracking
# ---------------------------------------------------------------------------

DEFAULT_SLA_MINUTES: Dict[int, int] = {
    5: 5,     # critical
    4: 15,    # high
    3: 30,    # medium
    2: 60,    # low
    1: 120,   # informational
}


def check_sla_deadlines(
    incidents: List[Incident],
    sla_config: Optional[Dict[int, int]] = None,
    now: Optional[datetime] = None,
) -> List[Dict[str, Any]]:
    """Find incidents approaching or past their SLA deadline.

    Returns a list of dicts with incident info and minutes remaining.
    """
    config = sla_config or DEFAULT_SLA_MINUTES
    now = now or datetime.now(timezone.utc)
    results: List[Dict[str, Any]] = []

    for incident in incidents:
        if incident.status in (IncidentStatus.RESOLVED, IncidentStatus.CLOSED):
            continue

        sla_minutes = config.get(incident.severity, 60)
        elapsed = (now - incident.created_at).total_seconds() / 60.0
        remaining = sla_minutes - elapsed

        if remaining <= sla_minutes * 0.2:  # within 20% of deadline
            results.append({
                "incident_id": str(incident.id),
                "severity": incident.severity,
                "sla_minutes": sla_minutes,
                "remaining_minutes": round(remaining, 2),
                "breached": remaining <= 0,
            })

    return sorted(results, key=lambda r: r["remaining_minutes"])


# ---------------------------------------------------------------------------
# Async task scheduling
# ---------------------------------------------------------------------------

async def schedule_async_task(
    coro_fn: Callable[..., Coroutine],
    delay_seconds: float,
    timeout_seconds: Optional[float] = None,
    args: tuple = (),
    kwargs: Optional[Dict[str, Any]] = None,
) -> Any:
    """Schedule an async task with optional timeout.

    """
    await asyncio.sleep(delay_seconds)

    coro = coro_fn(*args, **(kwargs or {}))

    if timeout_seconds is not None:
        return await asyncio.wait_for(coro, timeout=timeout_seconds)

    return await coro


async def recurring_task(
    fn: Callable[..., Coroutine],
    interval_seconds: float,
    max_iterations: Optional[int] = None,
) -> None:
    """Run an async function periodically.

    """
    iterations = 0
    while max_iterations is None or iterations < max_iterations:
        try:
            task = asyncio.create_task(fn())
            await task
        except asyncio.CancelledError:
            logger.warning("Recurring task cancelled, ignoring...")
            continue
        except Exception as e:
            logger.error("Recurring task failed: %s", str(e))

        iterations += 1
        await asyncio.sleep(interval_seconds)


# ---------------------------------------------------------------------------
# Task registry
# ---------------------------------------------------------------------------

class TaskRegistry:
    """Registry for scheduled tasks."""

    def __init__(self) -> None:
        self._tasks: Dict[str, ScheduledTask] = {}

    def register(self, task: ScheduledTask) -> None:
        """Add a task to the registry."""
        self._tasks[task.task_id] = task

    def get(self, task_id: str) -> Optional[ScheduledTask]:
        return self._tasks.get(task_id)

    def due_tasks(self, now: Optional[datetime] = None) -> List[ScheduledTask]:
        """Return all tasks that are due for execution."""
        return [t for t in self._tasks.values() if not t.executed and t.is_due(now)]

    def execute_due(self, now: Optional[datetime] = None) -> List[Dict[str, Any]]:
        """Execute all due tasks and return results."""
        results: List[Dict[str, Any]] = []
        for task in self.due_tasks(now):
            try:
                result = task.execute()
                results.append({
                    "task_id": task.task_id,
                    "success": True,
                    "result": result,
                })
            except Exception as e:
                results.append({
                    "task_id": task.task_id,
                    "success": False,
                    "error": str(e),
                })
        return results

    def pending_count(self) -> int:
        return sum(1 for t in self._tasks.values() if not t.executed)

    def clear(self) -> None:
        self._tasks.clear()


# ---------------------------------------------------------------------------
# Background task scheduling
# ---------------------------------------------------------------------------

async def schedule_background_update(
    state: Dict[str, Any],
    update_fn: Callable[[Dict[str, Any]], None],
) -> Dict[str, Any]:
    """Schedule a background task to update shared state."""
    task_state = state

    async def _background():
        update_fn(task_state)

    asyncio.create_task(_background())

    # Caller continues using ``state`` while _background mutates it concurrently
    return state


# ---------------------------------------------------------------------------
# Chord pattern (parallel tasks + callback)
# ---------------------------------------------------------------------------

_chord_completed: Dict[str, int] = {}


def chord_callback_check(
    chord_id: str,
    total: int,
    callback: Callable[[], Any],
) -> bool:
    """Record one task completion and fire the callback when all are done."""
    if chord_id not in _chord_completed:
        _chord_completed[chord_id] = 0

    _chord_completed[chord_id] += 1  # non-atomic read-modify-write
    current = _chord_completed[chord_id]

    if current == total:
        callback()
        del _chord_completed[chord_id]
        return True

    return False


# ---------------------------------------------------------------------------
# Per-request thread pool (anti-pattern)
# ---------------------------------------------------------------------------

def run_in_thread_pool(fn: Callable[..., Any], *args: Any) -> Any:
    """Execute a blocking function in a thread pool."""
    executor = ThreadPoolExecutor()
    try:
        future = executor.submit(fn, *args)
        return future.result()
    finally:
        # Each executor's threads are never cleaned up promptly
        pass


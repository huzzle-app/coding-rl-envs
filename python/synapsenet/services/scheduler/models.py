"""Scheduler service models."""


class ScheduledJob:
    """Scheduled job model."""

    def __init__(self, job_id, schedule, task_name, args=None):
        self.job_id = job_id
        self.schedule = schedule
        self.task_name = task_name
        self.args = args or {}
        self.is_active = True
        self.last_run = None
        self.next_run = None

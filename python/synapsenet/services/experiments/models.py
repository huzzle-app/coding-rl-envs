"""Experiments service models."""


class Experiment:
    """Experiment tracking model."""

    def __init__(self, experiment_id, name, model_id, parent_id=None):
        self.experiment_id = experiment_id
        self.name = name
        self.model_id = model_id
        self.parent_id = parent_id
        self.metrics = {}
        self.hyperparameters = {}
        self.tags = []
        self.status = "created"

"""
SynapseNet Shared Modules
Terminal Bench v2 - AI/ML Platform Shared Code

BUG L1: Circular import chain between shared.ml and shared.clients
The import of ServiceClient from shared.clients triggers an import of
shared.ml.model_loader which imports shared.clients.base, creating a cycle.
"""

# shared.clients.base imports shared.ml.model_loader
# shared.ml.model_loader imports shared.clients.base
from shared.clients import ServiceClient
from shared.ml import ModelLoader
from shared.events import EventBus

__all__ = ['ServiceClient', 'ModelLoader', 'EventBus']

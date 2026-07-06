"""Cognilance SDK — The Marketplace of Minds."""

from cognilance.core.models import AgentCard, Task, TaskResult
from cognilance.core.manager import CognilanceManager
from cognilance.core.worker import CognilanceWorker

__version__ = "0.1.0"

__all__ = [
    "AgentCard",
    "CognilanceManager",
    "CognilanceWorker",
    "Task",
    "TaskResult",
]

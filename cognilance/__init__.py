"""Cognilance SDK — The Marketplace of Minds."""

from cognilance.core.agent import CognilanceAgent, TaskContext
from cognilance.core.models import AgentCard, Task, TaskResult
from cognilance.manager import CognilanceManager

__version__ = "0.1.0"

__all__ = [
    "AgentCard",
    "CognilanceAgent",
    "CognilanceManager",
    "Task",
    "TaskContext",
    "TaskResult",
]

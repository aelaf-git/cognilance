"""Result of CognilanceManager.hire — TaskResult plus optional escrow handle."""

from __future__ import annotations

from dataclasses import dataclass

from cognilance.core.models import TaskResult
from cognilance.payments.models import HirePayment


@dataclass
class HireResult:
    """Backward-compatible wrapper: attributes of TaskResult are reachable on self."""

    result: TaskResult
    payment: HirePayment | None = None

    @property
    def output(self):
        return self.result.output

    @property
    def status(self):
        return self.result.status

    @property
    def id(self):
        return self.result.id

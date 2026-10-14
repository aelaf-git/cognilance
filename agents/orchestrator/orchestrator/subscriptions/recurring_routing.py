"""Shim — prefer orchestrator.routing.recurring."""

from pipeline.routing.recurring import recurring_subtasks_for_query

__all__ = ["recurring_subtasks_for_query"]

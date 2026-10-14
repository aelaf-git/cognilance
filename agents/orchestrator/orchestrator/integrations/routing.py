"""Shim — prefer orchestrator.routing / orchestrator.presenters."""

from tools.presenters.results import (
    format_calendar_list_result,
    format_document_result,
    format_gmail_list_result,
    format_recurring_result,
    format_subscription_result,
)
from pipeline.routing.integrations import integration_subtasks_for_query

__all__ = [
    "integration_subtasks_for_query",
    "format_calendar_list_result",
    "format_document_result",
    "format_gmail_list_result",
    "format_recurring_result",
    "format_subscription_result",
]

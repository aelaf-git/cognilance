"""Startup validation of agents, tools, and pipelines.

Nothing is registered at runtime: agents come from ``agents/*/agent.yaml``,
tools from ``tools/*/manifest.yaml``, pipelines from ``pipelines/*/graph.py``.
This module cross-checks them and surfaces problems early.
"""

from __future__ import annotations

from core.registry.loader import RegistryError, RegistryReport, validate_all

__all__ = ["RegistryError", "RegistryReport", "validate_all"]

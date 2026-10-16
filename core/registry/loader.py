from __future__ import annotations

import importlib
import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


class RegistryError(RuntimeError):
    """Raised in strict mode when manifests are inconsistent."""


@dataclass
class RegistryReport:
    agents: list[str] = field(default_factory=list)
    tools: list[str] = field(default_factory=list)
    pipelines: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors

    def summary(self) -> str:
        return (
            f"agents={len(self.agents)} tools={len(self.tools)} "
            f"pipelines={len(self.pipelines)} errors={len(self.errors)} "
            f"warnings={len(self.warnings)}"
        )


def _check_tools(report: RegistryReport) -> None:
    from tools.registry import load_manifests

    try:
        manifests = load_manifests()
    except Exception as exc:  # pragma: no cover - manifest syntax errors
        report.errors.append(f"tools: failed to load manifests: {exc}")
        return
    for name, manifest in sorted(manifests.items()):
        report.tools.append(name)
        if not manifest.actions:
            report.warnings.append(f"tools/{name}: manifest declares no actions")
        try:
            importlib.import_module(f"tools.{name}.tool")
        except Exception as exc:
            report.errors.append(f"tools/{name}: cannot import tool.py: {exc}")


def _check_agents(report: RegistryReport) -> None:
    from agents.loader import load_roles
    from tools.registry import validate_tool_ids

    try:
        roles = load_roles()
    except Exception as exc:
        report.errors.append(f"agents: failed to load agent.yaml files: {exc}")
        return
    if "coordinator" not in roles:
        report.errors.append("agents: missing coordinator/agent.yaml")
    for role_id, pack in sorted(roles.items()):
        report.agents.append(role_id)
        if not pack.instructions.strip():
            report.warnings.append(f"agents/{role_id}: empty system prompt")
        unknown = validate_tool_ids(list(pack.tools))
        if unknown:
            report.errors.append(f"agents/{role_id}: unknown tools {unknown}")
        if pack.schema_path and pack.path is not None:
            if not (pack.path / pack.schema_path).is_file():
                report.errors.append(f"agents/{role_id}: schema file {pack.schema_path} missing")
            else:
                try:
                    mod = importlib.import_module(f"agents.{role_id}.schema")
                    if not hasattr(mod, "Result"):
                        report.warnings.append(f"agents/{role_id}: schema.py has no Result model")
                except Exception as exc:
                    report.errors.append(f"agents/{role_id}: schema import failed: {exc}")


def _check_pipelines(report: RegistryReport) -> None:
    from pipelines import available_pipelines, get_pipeline

    for name in available_pipelines():
        report.pipelines.append(name)
        try:
            mod = get_pipeline(name)
        except Exception as exc:
            report.errors.append(f"pipelines/{name}: import failed: {exc}")
            continue
        if not callable(getattr(mod, "ensure_graph", None)):
            report.errors.append(f"pipelines/{name}: graph.py must define ensure_graph()")


def validate_all(*, strict: bool = False, log: bool = True) -> RegistryReport:
    """Validate tools, agents, and pipelines. Raise in strict mode on errors."""
    report = RegistryReport()
    _check_tools(report)
    _check_agents(report)
    _check_pipelines(report)
    if log:
        for w in report.warnings:
            logger.warning("registry: %s", w)
        for e in report.errors:
            logger.error("registry: %s", e)
        logger.info("registry: %s", report.summary())
    if strict and report.errors:
        raise RegistryError("; ".join(report.errors))
    return report

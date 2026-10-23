"""Load agent role packs from ``agents/<id>/agent.yaml``.

Each agent folder contains:

* ``agent.yaml`` - id, name, model, allowed tool ids, skills, prompt path, schema path
* ``prompts/``   - markdown prompt files referenced from the manifest
* ``schema.py``  - pydantic result model (``Result``) for structured outputs

``RolePack`` keeps the same shape the pipeline used before manifests existed.
"""

from __future__ import annotations

import importlib
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

AGENTS_DIR = Path(__file__).resolve().parent
COORDINATOR_ID = "coordinator"


@dataclass(frozen=True)
class RolePack:
    id: str
    name: str
    instructions: str
    tools: tuple[str, ...] = ()
    skills: tuple[str, ...] = ()
    model: str = "default"
    prompts: dict[str, str] = field(default_factory=dict)
    schema_path: str | None = None
    path: Path | None = None
    description: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "instructions": self.instructions,
            "description": self.description or self.instructions,
            "tools": list(self.tools),
            "skills": list(self.skills),
            "model": self.model,
        }

    def prompt(self, key: str = "system") -> str:
        return self.prompts.get(key) or self.instructions

    def result_schema(self) -> Any | None:
        """Import ``schema.Result`` for this agent if present."""
        if not self.schema_path or not self.path:
            return None
        module = importlib.import_module(f"agents.{self.path.name}.{Path(self.schema_path).stem}")
        return getattr(module, "Result", None)


def _read_prompt(agent_dir: Path, rel: str) -> str:
    path = agent_dir / rel
    return path.read_text().strip() if path.is_file() else ""


def _parse(agent_dir: Path) -> RolePack:
    raw = yaml.safe_load((agent_dir / "agent.yaml").read_text()) or {}
    prompts_raw = raw.get("prompts") or {}
    if isinstance(prompts_raw, str):
        prompts_raw = {"system": prompts_raw}
    prompts = {str(k): _read_prompt(agent_dir, str(v)) for k, v in prompts_raw.items()}
    instructions = str(raw.get("instructions") or "").strip() or prompts.get("system", "")
    return RolePack(
        id=str(raw.get("id") or agent_dir.name),
        name=str(raw.get("name") or agent_dir.name.replace("_", " ").title()),
        instructions=instructions,
        tools=tuple(str(t) for t in (raw.get("tools") or [])),
        skills=tuple(str(s) for s in (raw.get("skills") or [])),
        model=str(raw.get("model") or "default"),
        prompts=prompts,
        schema_path=raw.get("schema"),
        path=agent_dir,
        description=str(raw.get("description") or "").strip(),
    )


@lru_cache(maxsize=1)
def load_roles() -> dict[str, RolePack]:
    roles: dict[str, RolePack] = {}
    for manifest in sorted(AGENTS_DIR.glob("*/agent.yaml")):
        pack = _parse(manifest.parent)
        roles[pack.id] = pack
    return roles


_LEGACY_IDS = {
    "reporter": "report_writer",
    "follow_up": "email_agent",
    "followup": "email_agent",
    "email": "email_agent",
}


def normalize_role_id(role_id: str) -> str:
    key = role_id.strip().lower().replace("-", "_")
    return _LEGACY_IDS.get(key, key)


def get_role(role_id: str) -> RolePack | None:
    return load_roles().get(normalize_role_id(role_id))


def specialists() -> tuple[RolePack, ...]:
    return tuple(p for pid, p in load_roles().items() if pid != COORDINATOR_ID)


def specialist_ids() -> tuple[str, ...]:
    return tuple(p.id for p in specialists())


def coordinator() -> RolePack:
    pack = load_roles().get(COORDINATOR_ID)
    if pack is None:
        raise RuntimeError("agents/coordinator/agent.yaml is missing")
    return pack


class _LazyRoles(dict):
    """Dict view that resolves on first access (keeps ``ROLES[...]`` style imports working)."""

    def _load(self) -> None:
        if not super().__len__():
            super().update(load_roles())

    def __getitem__(self, key):  # type: ignore[override]
        self._load()
        return super().__getitem__(normalize_role_id(key))

    def get(self, key, default=None):  # type: ignore[override]
        self._load()
        return super().get(normalize_role_id(key), default)

    def __contains__(self, key):  # type: ignore[override]
        self._load()
        return super().__contains__(normalize_role_id(str(key)))

    def items(self):  # type: ignore[override]
        self._load()
        return super().items()

    def values(self):  # type: ignore[override]
        self._load()
        return super().values()

    def keys(self):  # type: ignore[override]
        self._load()
        return super().keys()

    def __iter__(self):
        self._load()
        return super().__iter__()

    def __len__(self):
        self._load()
        return super().__len__()


ROLES: dict[str, RolePack] = _LazyRoles()


class _LazySpecialists:
    def _items(self) -> tuple[RolePack, ...]:
        return specialists()

    def __iter__(self):
        return iter(self._items())

    def __len__(self):
        return len(self._items())

    def __getitem__(self, idx):
        return self._items()[idx]


SPECIALISTS = _LazySpecialists()

__all__ = [
    "AGENTS_DIR",
    "COORDINATOR_ID",
    "ROLES",
    "SPECIALISTS",
    "RolePack",
    "coordinator",
    "get_role",
    "load_roles",
    "normalize_role_id",
    "specialist_ids",
    "specialists",
]

"""Email follow-up: email_agent drafts a chase; sending stays behind approval."""

from __future__ import annotations

import uuid
from typing import Any

from pipelines.shared.build import BoardPipeline
from pipelines.shared.state import BoardTaskState


def preset(query: str) -> list[BoardTaskState]:
    context = query.strip() or "the pending thread"
    return [
        {
            "id": str(uuid.uuid4()),
            "title": "Draft follow-up email",
            "instruction": (
                f"Draft a short, polite follow-up email about: {context}. "
                "Do not send; return the draft for review."
            ),
            "assignee_role": "email_agent",
            "status": "open",
            "depends_on": [],
            "result_text": "",
            "result_json": {},
        }
    ]


PIPELINE = BoardPipeline(name="email_followup", title="Email follow-up", preset=preset)


async def init_graph() -> None:
    await PIPELINE.init_graph()


async def ensure_graph(*, with_checkpointer: bool = True) -> Any:
    return await PIPELINE.ensure_graph(with_checkpointer=with_checkpointer)


graph = PIPELINE.compile_for_studio()

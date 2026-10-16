"""Concept note: quick background research, then concept_note_writer drafts."""

from __future__ import annotations

import uuid
from typing import Any

from pipelines.shared.build import BoardPipeline
from pipelines.shared.state import BoardTaskState


def preset(query: str) -> list[BoardTaskState]:
    research_id = str(uuid.uuid4())
    idea = query.strip() or "the proposed project"
    return [
        {
            "id": research_id,
            "title": "Background for concept note",
            "instruction": (
                f"Find 3 credible references or comparable initiatives for: {idea}. "
                "Return title, url and one-line relevance for each."
            ),
            "assignee_role": "researcher",
            "status": "open",
            "depends_on": [],
            "result_text": "",
            "result_json": {},
        },
        {
            "id": str(uuid.uuid4()),
            "title": "Draft concept note",
            "instruction": (
                f"Draft a concept note for: {idea}. Use the standard concept note structure "
                "and create a Google Doc when Drive is connected; otherwise return the text."
            ),
            "assignee_role": "concept_note_writer",
            "status": "open",
            "depends_on": [research_id],
            "result_text": "",
            "result_json": {},
        },
    ]


PIPELINE = BoardPipeline(name="concept_note", title="Concept note", preset=preset)


async def init_graph() -> None:
    await PIPELINE.init_graph()


async def ensure_graph(*, with_checkpointer: bool = True) -> Any:
    return await PIPELINE.ensure_graph(with_checkpointer=with_checkpointer)


graph = PIPELINE.compile_for_studio()

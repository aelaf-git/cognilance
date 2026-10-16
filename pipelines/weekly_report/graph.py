"""Weekly report: researcher gathers updates, report_writer drafts the Doc."""

from __future__ import annotations

import uuid
from typing import Any

from pipelines.shared.build import BoardPipeline
from pipelines.shared.state import BoardTaskState


def preset(query: str) -> list[BoardTaskState]:
    research_id = str(uuid.uuid4())
    write_id = str(uuid.uuid4())
    topic = query.strip() or "this week's project activity"
    return [
        {
            "id": research_id,
            "title": "Gather this week's updates",
            "instruction": (
                f"Collect the most relevant updates for: {topic}. "
                "Return 3-6 bullet points with sources."
            ),
            "assignee_role": "researcher",
            "status": "open",
            "depends_on": [],
            "result_text": "",
            "result_json": {},
        },
        {
            "id": write_id,
            "title": "Draft weekly report document",
            "instruction": (
                f"Write a weekly report for: {topic}. Sections: Highlights, Progress, "
                "Risks, Next week. Create a Google Doc titled 'Weekly report' when Drive "
                "is connected; otherwise return the report text."
            ),
            "assignee_role": "report_writer",
            "status": "open",
            "depends_on": [research_id],
            "result_text": "",
            "result_json": {},
        },
    ]


PIPELINE = BoardPipeline(name="weekly_report", title="Weekly report", preset=preset)


async def init_graph() -> None:
    await PIPELINE.init_graph()


async def ensure_graph(*, with_checkpointer: bool = True) -> Any:
    return await PIPELINE.ensure_graph(with_checkpointer=with_checkpointer)


graph = PIPELINE.compile_for_studio()

"""Weekly report: project and GitHub evidence, then report_writer drafts the Doc."""

from __future__ import annotations

import uuid
from typing import Any

from pipelines.shared.build import BoardPipeline
from pipelines.shared.state import BoardTaskState


def _github_connected() -> bool:
    from core.broker.client import IntegrationClient
    from core.context.request import current_user_id

    user_id = str(current_user_id.get() or "").strip()
    if not user_id:
        return False
    try:
        return bool(IntegrationClient().is_connected(user_id, "github"))
    except Exception:
        return False


def preset(query: str) -> list[BoardTaskState]:
    topic = query.strip() or "this week's project activity"
    project_id = str(uuid.uuid4())
    depends = [project_id]
    tasks: list[BoardTaskState] = [
        {
            "id": project_id,
            "title": "Collect work tasks",
            "instruction": (
                f"List this organization's work tasks for: {topic}. "
                "Include each task id, title, status, and deadline. "
                "Completed work is status done. Delayed work is overdue or not done."
            ),
            "assignee_role": "project_agent",
            "status": "open",
            "depends_on": [],
            "result_text": "",
            "result_json": {},
        }
    ]
    if _github_connected():
        github_id = str(uuid.uuid4())
        depends.append(github_id)
        tasks.append(
            {
                "id": github_id,
                "title": "Collect GitHub activity",
                "instruction": (
                    f"List recent issues and pull requests for: {topic}. "
                    "Include their URLs and timestamps. "
                    "An empty GitHub response is the result."
                ),
                "assignee_role": "engineering_agent",
                "status": "open",
                "depends_on": [],
                "result_text": "",
                "result_json": {},
            }
        )
    tasks.append(
        {
            "id": str(uuid.uuid4()),
            "title": "Draft weekly report document",
            "instruction": (
                f"Write a weekly report for: {topic}. Sections: Completed work, Delayed work, "
                "and Recommendations. Every recommendation quotes a work-task id or a GitHub URL "
                "from the earlier results. Create a Google Doc titled 'Weekly report' when Drive "
                "is connected; otherwise return the report text."
            ),
            "assignee_role": "report_writer",
            "status": "open",
            "depends_on": depends,
            "result_text": "",
            "result_json": {},
        }
    )
    return tasks


PIPELINE = BoardPipeline(name="weekly_report", title="Weekly report", preset=preset)


async def init_graph() -> None:
    await PIPELINE.init_graph()


async def ensure_graph(*, with_checkpointer: bool = True) -> Any:
    return await PIPELINE.ensure_graph(with_checkpointer=with_checkpointer)


graph = PIPELINE.compile_for_studio()

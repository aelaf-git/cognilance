"""Generative UI Selector — picks the best React component for the final output."""

from __future__ import annotations

import uuid
from typing import Literal

from langchain_core.messages import AIMessage
from langgraph.graph.ui import push_ui_message
from pydantic import BaseModel, Field

from orchestrator.llm import get_llm
from orchestrator.state import State
from orchestrator.streaming import emit, emit_status, reveal_text

ComponentName = Literal["research-sources", "data-chart", "code-findings"]

UI_COMPONENTS = """- research-sources: research summaries with linked sources
- data-chart: bar or line charts for numeric series
- code-findings: code review findings with severity badges"""

SKILL_DEFAULT_UI: dict[str, ComponentName] = {
    "research": "research-sources",
    "data-analysis": "data-chart",
    "code-review": "code-findings",
}


class UISelection(BaseModel):
    component: ComponentName | None = Field(
        description=(
            "Rich UI component to render, or null when plain streamed text is enough.\n"
            f"{UI_COMPONENTS}"
        )
    )
    reasoning: str = Field(description="Why this component fits the output")


def _props_for_component(component: ComponentName, final_data: dict, text: str) -> dict:
    if component == "research-sources":
        return {
            "summary": final_data.get("summary") or text,
            "sources": final_data.get("sources") or [],
        }
    if component == "data-chart":
        return {
            "title": final_data.get("title"),
            "chartType": final_data.get("chartType", "bar"),
            "series": final_data.get("series") or [],
        }
    if component == "code-findings":
        return {
            "summary": final_data.get("summary") or text,
            "findings": final_data.get("findings") or [],
        }
    return {}


def _heuristic_component(state: State) -> ComponentName | None:
    plan = state.get("plan") or {}
    suggested = plan.get("suggested_ui")
    if suggested in {"research-sources", "data-chart", "code-findings"}:
        return suggested  # type: ignore[return-value]

    data = state.get("final_data") or {}
    if data.get("sources"):
        return "research-sources"
    if data.get("series"):
        return "data-chart"
    if data.get("findings"):
        return "code-findings"

    for result in state.get("subtask_results") or []:
        skill = None
        for subtask in state.get("subtasks") or []:
            if subtask.get("id") == result.get("subtask_id"):
                skill = subtask.get("skill")
                break
        if skill and skill in SKILL_DEFAULT_UI:
            return SKILL_DEFAULT_UI[skill]
    return None


async def ui_selector(state: State) -> dict:
    text = state.get("final_text") or ""
    data = state.get("final_data") or {}
    streamed = state.get("answer_streamed", False)

    if not streamed and text:
        reveal_text(text, event="answer")
        emit("answer_done", text=text)

    emit_status("Selecting generative UI…")
    component = _heuristic_component(state)

    if component is None and data:
        rich_keys = set(data.keys()) - {"body"}
        if rich_keys:
            llm = get_llm(temperature=0).with_structured_output(UISelection)
            decision: UISelection = await llm.ainvoke(
                [
                    {
                        "role": "system",
                        "content": (
                            "Pick the best rich UI component for this output. "
                            "Set component to null when plain text is sufficient.\n\n"
                            f"{UI_COMPONENTS}"
                        ),
                    },
                    {
                        "role": "user",
                        "content": (
                            f"Final text:\n{text}\n\n"
                            f"Structured data keys: {list(rich_keys)}"
                        ),
                    },
                ]
            )  # type: ignore[assignment]
            component = decision.component

    message = AIMessage(id=str(uuid.uuid4()), content=text)

    if component:
        props = _props_for_component(component, data, text)
        if props and any(props.values()):
            emit("ui", name=component, props=props)
            push_ui_message(component, props, message=message)

    return {"messages": [message]}

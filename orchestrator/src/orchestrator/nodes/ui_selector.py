"""Generative UI Selector — picks the best React component for the final output."""

from __future__ import annotations

import re
import uuid
from typing import Any, Literal

from langchain_core.messages import AIMessage
from langgraph.graph.ui import push_ui_message
from pydantic import BaseModel, Field, field_validator

from orchestrator.llm import get_llm
from orchestrator.state import State
from orchestrator.streaming import emit, emit_status, reveal_text

ComponentName = Literal["email-draft", "research-sources", "data-chart", "python-code"]

UI_COMPONENTS = """- email-draft: composed email with to, subject, body, and send status
- research-sources: research summaries with linked sources
- data-chart: bar or line charts for numeric series
- python-code: Python source code with filename and summary"""

SKILL_DEFAULT_UI: dict[str, ComponentName] = {
    "email-writing": "email-draft",
    "research": "research-sources",
    "data-analysis": "data-chart",
    "python-code": "python-code",
}

SUGGESTED_UI_ALIASES: dict[str, ComponentName] = {
    "code-findings": "python-code",
    "code-review": "python-code",
    "code": "python-code",
}


class UISelection(BaseModel):
    component: ComponentName | None = Field(
        default=None,
        description=(
            "Rich UI component to render. Omit when plain text is enough.\n"
            f"{UI_COMPONENTS}"
        ),
    )
    reasoning: str = Field(default="", description="Why this component fits the output")

    @field_validator("component", mode="before")
    @classmethod
    def _coerce_null_component(cls, value: Any) -> ComponentName | None:
        if value is None:
            return None
        if isinstance(value, str) and value.strip().lower() in {"", "null", "none", "n/a"}:
            return None
        return value


def _gather_data(state: State) -> dict[str, Any]:
    """Merge structured payloads from final_data and hired subtask results."""
    merged: dict[str, Any] = dict(state.get("final_data") or {})
    for result in state.get("subtask_results") or []:
        for key, value in (result.get("data") or {}).items():
            if key not in merged or merged[key] in (None, "", [], {}):
                merged[key] = value
            elif isinstance(merged[key], list) and isinstance(value, list):
                merged[key] = merged[key] + value

    text = state.get("final_text") or ""
    if not merged.get("code") and text:
        match = re.search(r"```(?:python)?\s*\n(.*?)```", text, re.DOTALL | re.IGNORECASE)
        if match:
            merged.setdefault("filename", "solution.py")
            merged["code"] = match.group(1).strip()
    return merged


def _normalize_suggested(name: str | None) -> ComponentName | None:
    if not name:
        return None
    if name in {"email-draft", "research-sources", "data-chart", "python-code"}:
        return name  # type: ignore[return-value]
    return SUGGESTED_UI_ALIASES.get(name)


def _props_for_component(component: ComponentName, data: dict[str, Any], text: str) -> dict:
    if component == "email-draft":
        return {
            "to": data.get("to") or "",
            "subject": data.get("subject") or "",
            "body": data.get("body") or text,
            "tone": data.get("tone") or "professional",
            "status": data.get("status") or "draft",
            "gmail_message_id": data.get("gmail_message_id"),
        }
    if component == "research-sources":
        return {
            "summary": data.get("summary") or text,
            "sources": data.get("sources") or [],
        }
    if component == "data-chart":
        return {
            "title": data.get("title"),
            "chartType": data.get("chartType", "bar"),
            "series": data.get("series") or [],
        }
    if component == "python-code":
        code = data.get("code") or ""
        return {
            "summary": data.get("summary") or text,
            "filename": data.get("filename") or "solution.py",
            "code": code,
        }
    return {}


def _props_have_content(component: ComponentName, props: dict[str, Any]) -> bool:
    if component == "email-draft":
        return bool(str(props.get("body") or "").strip())
    if component == "research-sources":
        return bool(props.get("sources"))
    if component == "data-chart":
        return bool(props.get("series"))
    if component == "python-code":
        return bool(str(props.get("code") or "").strip())
    return bool(props)


def _heuristic_component(state: State, data: dict[str, Any]) -> ComponentName | None:
    plan = state.get("plan") or {}
    suggested = _normalize_suggested(plan.get("suggested_ui"))
    if suggested:
        return suggested

    if data.get("body") and data.get("subject"):
        return "email-draft"
    if data.get("sources"):
        return "research-sources"
    if data.get("series"):
        return "data-chart"
    if data.get("code"):
        return "python-code"

    for result in state.get("subtask_results") or []:
        result_data = result.get("data") or {}
        if result_data.get("body") and result_data.get("subject"):
            return "email-draft"
        if result_data.get("sources"):
            return "research-sources"
        if result_data.get("series"):
            return "data-chart"
        if result_data.get("code"):
            return "python-code"

    for result in state.get("subtask_results") or []:
        skill = None
        for subtask in state.get("subtasks") or []:
            if subtask.get("id") == result.get("subtask_id"):
                skill = subtask.get("skill")
                break
        if skill and skill in SKILL_DEFAULT_UI:
            return SKILL_DEFAULT_UI[skill]
    return None


def _data_suggests_rich_ui(data: dict[str, Any]) -> bool:
    if data.get("body") and data.get("subject"):
        return True
    if data.get("sources") or data.get("series") or data.get("code"):
        return True
    return isinstance(data.get("chartType"), str)


async def ui_selector(state: State) -> dict:
    text = state.get("final_text") or ""
    data = _gather_data(state)
    streamed = state.get("answer_streamed", False)

    if not streamed and text:
        reveal_text(text, event="answer")
        emit("answer_done", text=text)

    emit_status("Selecting generative UI…")
    component = _heuristic_component(state, data)

    if component is None and _data_suggests_rich_ui(data):
        preview = {
            key: (str(value)[:400] + "…" if len(str(value)) > 400 else value)
            for key, value in data.items()
            if key != "body"
        }
        try:
            llm = get_llm(temperature=0).with_structured_output(UISelection)
            decision: UISelection = await llm.ainvoke(
                [
                    {
                        "role": "system",
                        "content": (
                            "Pick the best rich UI component for this output. "
                            "Use python-code when structured data includes runnable Python source. "
                            "Leave component unset when plain text is sufficient.\n\n"
                            f"{UI_COMPONENTS}"
                        ),
                    },
                    {
                        "role": "user",
                        "content": (
                            f"Final text:\n{text}\n\n"
                            f"Structured data preview:\n{preview}"
                        ),
                    },
                ]
            )  # type: ignore[assignment]
            component = decision.component
        except Exception:
            component = None

    message = AIMessage(id=str(uuid.uuid4()), content=text)

    if component:
        props = _props_for_component(component, data, text)
        if _props_have_content(component, props):
            emit("ui", name=component, props=props)
            emit(
                "gen_ui_selected",
                component=component,
                props=props,
            )
            push_ui_message(component, props, message=message)
        else:
            emit(
                "gen_ui_selected",
                component=None,
                reason=f"No rich content for {component}",
            )

    return {"messages": [message]}

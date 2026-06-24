"""UI agent — streams the answer, then picks and emits generative UI."""

from __future__ import annotations

import uuid
from typing import Literal

from langchain_core.messages import AIMessage
from langgraph.graph.ui import push_ui_message
from pydantic import BaseModel, Field

from orchestrator.llm import get_llm, last_user_text
from orchestrator.nodes.planner import UI_COMPONENTS
from orchestrator.state import State
from orchestrator.streaming import emit, emit_status, reveal_text, stream_llm

ComponentName = Literal["research-sources", "data-chart", "code-findings", "text-card"]

SKILL_DEFAULT_UI: dict[str, ComponentName] = {
    "research": "research-sources",
    "data-analysis": "data-chart",
    "code-review": "code-findings",
}

ANSWER_SYSTEM = (
    "You are the Cognilance orchestrator. Answer the user directly and concisely. "
    "Mention which marketplace specialist could help if relevant."
)


class UIDecision(BaseModel):
    component: ComponentName = Field(
        description=f"UI component to render.\n{UI_COMPONENTS}"
    )
    reasoning: str = Field(description="Why this component fits the request and data")


def _props_for_component(component: ComponentName, hire_result: dict, text: str) -> dict:
    data = hire_result.get("data") or {}

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
    if component == "code-findings":
        return {
            "summary": data.get("summary") or text,
            "findings": data.get("findings") or [],
        }
    return {"title": "Response", "body": text}


async def ui_agent(state: State) -> dict:
    hire_result = state.get("hire_result") or {}
    plan = state.get("plan") or {}
    query = last_user_text(state.get("messages", []))
    mode = hire_result.get("mode", "general")
    preset_text = hire_result.get("text") or ""

    if mode == "error":
        reveal_text(preset_text, event="answer")
        emit("answer_done", text=preset_text)
        message = AIMessage(id=str(uuid.uuid4()), content=preset_text)
        return {"messages": [message]}

    emit_status("Choosing generative UI component…")
    suggested = plan.get("suggested_ui")
    skill = hire_result.get("skill")
    default_component = SKILL_DEFAULT_UI.get(skill or "", "text-card")

    llm = get_llm(temperature=0).with_structured_output(UIDecision)
    decision: UIDecision = await llm.ainvoke(
        [
            {
                "role": "system",
                "content": (
                    "You are the Cognilance UI agent. Choose the best generative UI "
                    "component for the user's request and the specialist output.\n\n"
                    f"Available components:\n{UI_COMPONENTS}\n\n"
                    f"Planner suggested UI: {suggested or default_component}\n"
                    f"Hire mode: {mode}\n"
                    f"Skill used: {skill or 'none'}"
                ),
            },
            {
                "role": "user",
                "content": (
                    f"User request:\n{query}\n\n"
                    f"Agent text:\n{preset_text or '(will be generated)'}\n\n"
                    f"Structured data keys: {list((hire_result.get('data') or {}).keys())}"
                ),
            },
        ]
    )  # type: ignore[assignment]

    emit("ui_reasoning", text=decision.reasoning)

    component = decision.component
    if mode == "general" and component != "text-card":
        component = "text-card"

    emit_status("Writing answer…")
    if mode == "general":
        text = await stream_llm(
            get_llm(temperature=0.4),
            [
                {"role": "system", "content": ANSWER_SYSTEM},
                {"role": "user", "content": query},
            ],
            event="answer",
        )
    else:
        text = preset_text
        reveal_text(text, event="answer")

    emit("answer_done", text=text)

    props = _props_for_component(component, hire_result, text)
    emit("ui", name=component, props=props)

    message = AIMessage(id=str(uuid.uuid4()), content=text)
    push_ui_message(component, props, message=message)

    meta_parts: list[str] = []
    if plan.get("reasoning"):
        meta_parts.append(f"plan: {plan['reasoning']}")
    if hire_result.get("agent_name"):
        meta_parts.append(f"hired: {hire_result['agent_name']}")
    elif mode == "general":
        meta_parts.append("mode: general")
    meta_parts.append(f"ui: {decision.reasoning}")
    message.additional_kwargs["orchestrator_meta"] = " · ".join(meta_parts)
    return {"messages": [message]}

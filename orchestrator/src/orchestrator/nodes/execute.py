"""Executor — runs the plan step-by-step, then hires or defers to direct answer."""

from __future__ import annotations

from cognilance import CognilanceManager

from orchestrator.llm import last_user_text
from orchestrator.state import HireResult, State
from orchestrator.streaming import emit, emit_status


async def _run_step(index: int, title: str, detail: str) -> None:
    emit("step_start", index=index, title=title, detail=detail)
    emit_status(f"Step {index + 1}: {title}")


async def _finish_step(index: int) -> None:
    emit("step_done", index=index)


async def execute(state: State) -> dict:
    plan = state.get("plan") or {}
    query = last_user_text(state.get("messages", []))
    steps = plan.get("steps") or []
    action = plan.get("action", "general")

    emit("execution_start")

    for index, step in enumerate(steps):
        title = step.get("title", f"Step {index + 1}")
        detail = step.get("detail", "")
        await _run_step(index, title, detail)
        await _finish_step(index)

    if action == "general":
        exec_index = len(steps)
        await _run_step(exec_index, "Answer directly", "Respond without hiring a specialist")
        hire_result: HireResult = {
            "mode": "general",
            "text": "",
            "data": {},
            "skill": None,
            "agent_name": None,
        }
        await _finish_step(exec_index)
        emit("execution_done")
        return {"hire_result": hire_result}

    skill = (plan.get("skill") or "").strip()
    if not skill:
        hire_result = {
            "mode": "error",
            "text": "Plan chose hire but did not specify a skill.",
            "data": {},
            "skill": None,
            "agent_name": None,
        }
        emit("execution_done")
        return {"hire_result": hire_result}

    async with CognilanceManager(agent_name="Orchestrator") as manager:
        exec_index = len(steps)
        await _run_step(exec_index, f"Hire {skill} specialist", "Discover agent on registry and run task")
        agents = await manager.discover(skills=[skill], limit=5)
        if not agents:
            await _finish_step(exec_index)
            hire_result = {
                "mode": "error",
                "text": (
                    f"No agent offering the '{skill}' skill is online right now. "
                    "Start the matching agent in /agents and try again."
                ),
                "data": {},
                "skill": skill,
                "agent_name": None,
            }
            emit("execution_done")
            return {"hire_result": hire_result}

        chosen = agents[0]
        emit_status(f"Hiring {chosen.name}…")
        result = await manager.hire(chosen, input_text=query)
        await _finish_step(exec_index)
        hire_result = {
            "mode": "hired",
            "text": result.output.text or "",
            "data": result.output.data or {},
            "skill": skill,
            "agent_name": chosen.name,
        }
        emit("execution_done")
        return {"hire_result": hire_result}

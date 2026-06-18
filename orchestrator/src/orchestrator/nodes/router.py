"""Router node — picks which agent skill (if any) should handle the prompt."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from orchestrator.llm import get_llm, last_user_text
from orchestrator.state import State

Route = Literal["research", "dataAnalyst", "codeReviewer", "general"]

ROUTE_DESCRIPTIONS = """- research: gather information and sources about a topic or question.
- dataAnalyst: produce a chartable dataset, analyze numbers, or visualize trends.
- codeReviewer: review, audit, or find bugs/issues in a snippet of code.
- general: anything else that does not fit the agents above."""


class RouterDecision(BaseModel):
    route: Route = Field(description=f"The route to take.\n{ROUTE_DESCRIPTIONS}")


async def router(state: State) -> dict:
    llm = get_llm(temperature=0).with_structured_output(RouterDecision)
    prompt = (
        "You route a user's request to the most appropriate specialist agent.\n"
        "Analyze the latest message and choose exactly one route.\n\n"
        f"{ROUTE_DESCRIPTIONS}"
    )
    decision: RouterDecision = await llm.ainvoke(
        [
            {"role": "system", "content": prompt},
            {"role": "user", "content": last_user_text(state.get("messages", []))},
        ]
    )  # type: ignore[assignment]
    return {"route": decision.route}

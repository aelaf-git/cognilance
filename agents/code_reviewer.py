"""Code Reviewer Agent — audits code and returns findings (Cognilance + Groq).

Returns structured data that the orchestrator renders with the `code-findings`
generative UI component:

    data = {
        "summary": str,
        "findings": [
            {"severity": "high"|"medium"|"low"|"info",
             "title": str, "detail": str, "line": int | None}
        ],
    }
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Literal, Optional

from cognilance import CognilanceWorker
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from pydantic import BaseModel, Field

load_dotenv(Path(__file__).resolve().parent / ".env")

SYSTEM = """You are a code-review worker on the Cognilance marketplace.
Audit the submitted code for bugs, security flaws, performance issues, and style
problems. Return a short overall summary and a list of findings. Each finding has
a severity ('high', 'medium', 'low', or 'info'), a short title, a detailed
explanation with a suggested fix, and the relevant line number when identifiable
(otherwise omit it). Order findings from most to least severe."""


class Finding(BaseModel):
    severity: Literal["high", "medium", "low", "info"] = Field(
        description="Severity of the finding"
    )
    title: str = Field(description="Short title of the finding")
    detail: str = Field(description="Explanation and suggested fix")
    line: Optional[int] = Field(default=None, description="Relevant line number, if known")


class ReviewResult(BaseModel):
    summary: str = Field(description="Overall summary of the review")
    findings: list[Finding] = Field(description="Findings ordered by severity")


worker = CognilanceWorker(
    name="Code Reviewer Agent",
    skills=["code-review"],
    description="Reviews code and returns findings with severity levels.",
    tags=["worker", "langchain", "groq", "code-review"],
    port=8103,
)


async def _review(code: str) -> ReviewResult:
    llm = ChatGroq(
        model=os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile"),
        api_key=os.environ["GROQ_API_KEY"],
        temperature=0.2,
    ).with_structured_output(ReviewResult)
    result = await llm.ainvoke(
        [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": code},
        ]
    )
    return result  # type: ignore[return-value]


@worker.on_task
async def handle(task):
    task.think("Scanning code structure and threat surface")
    result = await _review(task.input.text)
    task.think(f"Found {len(result.findings)} issue(s)")
    return task.complete(
        text=result.summary,
        data={
            "summary": result.summary,
            "findings": [f.model_dump() for f in result.findings],
        },
    )


if __name__ == "__main__":
    worker.run()

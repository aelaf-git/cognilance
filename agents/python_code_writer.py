"""Python Code Writer Agent — generates Python code from a request (Cognilance + Groq).

Returns structured data that the orchestrator renders with the `python-code`
generative UI component:

    data = {
        "summary": str,
        "filename": str,
        "code": str,
    }
"""

from __future__ import annotations

import os
from pathlib import Path

from cognilance import CognilanceWorker
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from pydantic import BaseModel, Field

_ROOT_ENV = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(_ROOT_ENV)

SYSTEM = """You are a Python code-writing worker on the Cognilance marketplace.
Given a request, produce clean, idiomatic Python 3 code that solves the problem.
Include a short summary explaining the approach. Pick a sensible filename ending in
.py. Write complete, runnable code with any needed imports. Prefer clarity over
cleverness. Add brief inline comments only where the logic is non-obvious."""


class CodeResult(BaseModel):
    summary: str = Field(description="Brief explanation of the solution approach")
    filename: str = Field(description="Suggested filename, e.g. solution.py")
    code: str = Field(description="Complete Python source code")


worker = CognilanceWorker(
    name="Python Code Writer Agent",
    skills=["python-code"],
    description="Writes Python code from natural-language requests.",
    tags=["worker", "langchain", "groq", "python", "code-writing"],
    port=8103,
)


async def _write_code(request: str) -> CodeResult:
    llm = ChatGroq(
        model=os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile"),
        api_key=os.environ["GROQ_API_KEY"],
        temperature=0.2,
    ).with_structured_output(CodeResult)
    result = await llm.ainvoke(
        [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": request},
        ]
    )
    return result  # type: ignore[return-value]


@worker.on_task
async def handle(task):
    task.think("Analyzing the request and planning the implementation")
    result = await _write_code(task.input.text)
    task.think(f"Generated {result.filename}")
    return task.complete(
        text=result.summary,
        data={
            "summary": result.summary,
            "filename": result.filename,
            "code": result.code,
        },
    )


if __name__ == "__main__":
    worker.run()

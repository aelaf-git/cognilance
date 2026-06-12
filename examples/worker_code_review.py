"""Worker — Code Review (Cognilance + LangChain + Groq)."""

from __future__ import annotations

import os
from pathlib import Path

from cognilance import CognilanceWorker
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_groq import ChatGroq

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

SYSTEM = """You are a code-review worker on the Cognilance marketplace.
Audit code for bugs, security flaws, and style issues.
Respond with: Findings (bullets), Risk level, Suggested fix."""

worker = CognilanceWorker(
    name="Worker — Code Review",
    skills=["code-review", "security-audit", "python"],
    description="Reviews and secures code submissions.",
    tags=["worker", "langchain", "groq"],
    port=8001,
)


async def _groq(system: str, user: str) -> str:
    llm = ChatGroq(
        model=os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile"),
        api_key=os.environ["GROQ_API_KEY"],
        temperature=0.2,
    )
    msg = await llm.ainvoke([SystemMessage(content=system), HumanMessage(content=user)])
    return msg.content if isinstance(msg.content, str) else str(msg.content)


@worker.on_task
async def handle(task):
    task.think("Scanning code structure and threat surface")
    review = await _groq(SYSTEM, task.input.text)
    task.think("Packaging audit report")
    return task.complete(text=review, data={"role": "worker", "job": "code-review"})


if __name__ == "__main__":
    worker.chat()

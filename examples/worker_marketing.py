"""Worker — Marketing Copy (Cognilance + LangChain + Groq)."""

from __future__ import annotations

import os
from pathlib import Path

from cognilance import CognilanceWorker
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_groq import ChatGroq

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

SYSTEM = """You are a marketing-copy worker on the Cognilance marketplace.
Write punchy marketing copy: headlines, taglines, social posts, and CTAs.
Match the audience implied in the brief. Keep it vivid and concise."""

worker = CognilanceWorker(
    name="Worker — Marketing Copy",
    skills=["marketing", "copywriting", "social-media"],
    description="Writes marketing and social media copy.",
    tags=["worker", "langchain", "groq"],
    port=8002,
)


async def _groq(system: str, user: str) -> str:
    llm = ChatGroq(
        model=os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile"),
        api_key=os.environ["GROQ_API_KEY"],
        temperature=0.7,
    )
    msg = await llm.ainvoke([SystemMessage(content=system), HumanMessage(content=user)])
    return msg.content if isinstance(msg.content, str) else str(msg.content)


@worker.on_task
async def handle(task):
    task.think("Parsing brief and audience tone")
    copy = await _groq(SYSTEM, task.input.text)
    task.think("Finalizing campaign copy")
    return task.complete(text=copy, data={"role": "worker", "job": "marketing"})


if __name__ == "__main__":
    worker.chat()

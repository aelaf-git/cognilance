"""Research Agent — gathers sources and a summary for a topic (Cognilance + Groq).

Returns structured data that the orchestrator renders with the `research-sources`
generative UI component:

    data = {
        "summary": str,
        "sources": [{"title": str, "url": str, "snippet": str}],
    }
"""

from __future__ import annotations

import os
from pathlib import Path

from cognilance import CognilanceWorker
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from pydantic import BaseModel, Field

load_dotenv(Path(__file__).resolve().parent / ".env")

SYSTEM = """You are a research worker on the Cognilance marketplace.
Given a topic or question, produce a concise factual summary and a list of
relevant sources. Each source needs a descriptive title, a plausible URL, and a
one-sentence snippet explaining why it is relevant. Prefer authoritative sources.
Return between 3 and 6 sources."""


class Source(BaseModel):
    title: str = Field(description="Descriptive title of the source")
    url: str = Field(description="URL of the source")
    snippet: str = Field(description="One sentence on why this source is relevant")


class ResearchResult(BaseModel):
    summary: str = Field(description="Concise factual summary of the topic")
    sources: list[Source] = Field(description="Relevant sources (3-6 items)")


worker = CognilanceWorker(
    name="Research Agent",
    skills=["research"],
    description="Researches a topic and returns a summary with cited sources.",
    tags=["worker", "langchain", "groq", "research"],
    port=8101,
)


async def _research(query: str) -> ResearchResult:
    llm = ChatGroq(
        model=os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile"),
        api_key=os.environ["GROQ_API_KEY"],
        temperature=0.3,
    ).with_structured_output(ResearchResult)
    result = await llm.ainvoke(
        [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": query},
        ]
    )
    return result  # type: ignore[return-value]


@worker.on_task
async def handle(task):
    task.think("Scanning the topic and selecting sources")
    result = await _research(task.input.text)
    task.think(f"Compiled {len(result.sources)} sources")
    return task.complete(
        text=result.summary,
        data={
            "summary": result.summary,
            "sources": [s.model_dump() for s in result.sources],
        },
    )


if __name__ == "__main__":
    worker.run()

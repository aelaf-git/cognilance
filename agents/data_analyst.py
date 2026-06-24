"""Data Analyst Agent — turns a request into a chartable series (Cognilance + Groq).

Returns structured data that the orchestrator renders with the `data-chart`
generative UI component:

    data = {
        "title": str,
        "chartType": "bar" | "line",
        "series": [{"label": str, "value": float}],
    }
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Literal

from cognilance import CognilanceWorker
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from pydantic import BaseModel, Field

_ROOT_ENV = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(_ROOT_ENV)

SYSTEM = """You are a data-analysis worker on the Cognilance marketplace.
Given a request, produce a single chartable dataset. Choose a clear chart title,
pick the most appropriate chart type ('bar' for categorical comparisons, 'line'
for trends over time), and return a labeled numeric series. If the user provides
numbers, use them; otherwise produce a realistic illustrative dataset. Return
between 3 and 12 data points."""


class DataPoint(BaseModel):
    label: str = Field(description="Category or x-axis label")
    value: float = Field(description="Numeric value for this point")


class ChartResult(BaseModel):
    title: str = Field(description="Chart title")
    chartType: Literal["bar", "line"] = Field(description="Best-fit chart type")
    series: list[DataPoint] = Field(description="Data points (3-12 items)")


worker = CognilanceWorker(
    name="Data Analyst Agent",
    skills=["data-analysis"],
    description="Analyzes a request and returns a chartable dataset.",
    tags=["worker", "langchain", "groq", "data-analysis"],
    port=8102,
)


async def _analyze(query: str) -> ChartResult:
    llm = ChatGroq(
        model=os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile"),
        api_key=os.environ["GROQ_API_KEY"],
        temperature=0.2,
    ).with_structured_output(ChartResult)
    result = await llm.ainvoke(
        [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": query},
        ]
    )
    return result  # type: ignore[return-value]


@worker.on_task
async def handle(task):
    task.think("Shaping the dataset and choosing a chart type")
    result = await _analyze(task.input.text)
    task.think(f"Prepared a {result.chartType} chart with {len(result.series)} points")
    summary = f"{result.title}: {len(result.series)} data points ({result.chartType} chart)."
    return task.complete(
        text=summary,
        data={
            "title": result.title,
            "chartType": result.chartType,
            "series": [p.model_dump() for p in result.series],
        },
    )


if __name__ == "__main__":
    worker.run()

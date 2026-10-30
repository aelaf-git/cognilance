"""Structured LLM calls. Tests patch ``call_structured`` on this module."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel


async def call_structured(schema: type[BaseModel], prompt: str, temperature: float = 0.1) -> Any:
    from core.models.gateway import get_structured_llm

    llm = get_structured_llm(schema, temperature=temperature)
    return await llm.ainvoke(prompt)

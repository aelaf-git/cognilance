"""Thinking Agent — direct reasoning for simple tasks and subtask fallback."""

from __future__ import annotations

from langchain_core.messages import BaseMessage

from orchestrator.llm import get_llm, to_chat_messages
from orchestrator.streaming import reveal_text

THINKING_SYSTEM = """You are Cognilance replying in chat.

Rules:
- Output ONLY the final message the user should read — no reasoning, planning, or inner monologue.
- Never mention tools, APIs, subscribe_inbox, app:gmail, integrations, or orchestration.
- Never say "let me try", "I'll attempt", "please wait", or describe steps you will take.
- One to three short sentences. Warm and natural.
- If the user is acknowledging something already set up, confirm briefly and stop.
- If they need an action you cannot perform, say what they should do in plain language only."""


def build_thinking_system(*, capabilities: str = "") -> str:
    if not capabilities:
        return THINKING_SYSTEM
    return (
        f"{THINKING_SYSTEM}\n\n"
        f"Connected capabilities (do not name these in chat):\n{capabilities}\n\n"
        "If a required capability is not connected, tell the user to open Integrations "
        "and connect it — without naming internal tool slugs."
    )


async def run_thinking(
    instruction: str = "",
    *,
    stream: bool = True,
    conversation: list[BaseMessage] | None = None,
    capabilities: str = "",
) -> tuple[str, dict]:
    """Run the Thinking Agent; pass conversation for multi-turn context."""
    messages: list[dict[str, str]] = [
        {"role": "system", "content": build_thinking_system(capabilities=capabilities)}
    ]
    if conversation:
        messages.extend(to_chat_messages(conversation))
    elif instruction:
        messages.append({"role": "user", "content": instruction})

    response = await get_llm(temperature=0.3).ainvoke(messages)
    content = response.content
    text = content if isinstance(content, str) else str(content)
    if stream:
        reveal_text(text, event="answer")
    return text, {"body": text}

"""Thinking Agent — direct reasoning for simple tasks and subtask fallback."""

from __future__ import annotations

from langchain_core.messages import BaseMessage

from orchestrator.llm import get_llm, to_chat_messages
from orchestrator.streaming import stream_llm

THINKING_SYSTEM = """You are the Cognilance Thinking Agent. Use the full conversation history \
when answering — remember names, preferences, and facts the user shared earlier. \
Reason clearly and answer the user directly. Be concise and accurate. \
Do not mention internal orchestration unless explaining a missing integration."""


def build_thinking_system(*, capabilities: str = "") -> str:
    if not capabilities:
        return THINKING_SYSTEM
    return (
        f"{THINKING_SYSTEM}\n\n"
        f"Tool access for this user:\n{capabilities}\n\n"
    "If the user wants an action that needs a NOT CONNECTED integration, "
    "say which integration is required and that they must connect it at /integrations. "
    "Never describe plans, subtasks, or internal tools — either answer directly or "
    "state that an integration must be connected first. "
    "Never claim you sent email, created calendar events, edited Google Docs, "
    "or called external APIs unless that actually happened in execution results. "
    "If the user needs a connected integration, explain that the orchestrator "
    "will run it in the execution phase."
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
    if stream:
        text = await stream_llm(get_llm(temperature=0.4), messages, event="answer")
    else:
        response = await get_llm(temperature=0.4).ainvoke(messages)
        content = response.content
        text = content if isinstance(content, str) else str(content)
    return text, {"body": text}

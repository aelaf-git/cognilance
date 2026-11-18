"""Model thought summaries are streamed separately from the answer."""

from __future__ import annotations

import pytest
from langchain_core.messages import AIMessage

from core.models.gateway import ReasoningLLM


@pytest.mark.asyncio
async def test_ainvoke_emits_the_thought_and_keeps_the_answer(monkeypatch: pytest.MonkeyPatch) -> None:
    events: list[tuple[str, dict]] = []

    def capture(event: str, **data: object) -> None:
        events.append((event, data))

    monkeypatch.setattr("pipelines.shared.streaming.emit", capture)
    message = AIMessage(
        content=[
            {"type": "thinking", "thinking": "The user wants a file."},
            {"type": "text", "text": "Here is the file."},
        ]
    )

    class _FakeModel:
        async def ainvoke(self, *_args: object, **_kwargs: object) -> AIMessage:
            return message

    result = await ReasoningLLM(_FakeModel()).ainvoke("hi")  # type: ignore[arg-type]

    assert result.content == "Here is the file."
    thought = "".join(
        str(data.get("delta") or "") for event, data in events if event == "thinking"
    )
    assert thought == "The user wants a file."
    assert not any(event == "answer" for event, _data in events)

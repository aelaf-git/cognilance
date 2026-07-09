"""Minimal template agent for the Cognilance Agent Host developer portal."""

from __future__ import annotations

from cognilance import CognilanceWorker

worker = CognilanceWorker(
    name="Template Agent",
    skills=["template-demo"],
    description="Echoes your message — use as a starting point for custom agents.",
    tags=["template", "demo"],
    port=8104,
)


@worker.on_task
async def handle(task):
    text = task.input.text.strip()
    task.think("Processing your message")
    return task.complete(text=f"Template agent received: {text}")


if __name__ == "__main__":
    worker.run()

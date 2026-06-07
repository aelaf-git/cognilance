"""Example worker — gets hired, delivers work, does not hire others."""

from cognilance import CognilanceWorker

worker = CognilanceWorker(
    name="Echo Worker",
    skills=["echo", "general"],
    description="A minimal leaf worker for testing the SDK.",
    port=8001,
)


@worker.on_task
async def handle(task):
    return task.complete(text=f"Echo: {task.input.text}")


if __name__ == "__main__":
    worker.chat()

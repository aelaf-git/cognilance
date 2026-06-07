"""Example specialist agent — gets hired via A2A, can rehire others."""

from cognilance import CognilanceAgent

agent = CognilanceAgent(
    name="Echo Specialist",
    skills=["echo", "general"],
    description="A minimal specialist for testing the SDK.",
    port=8001,
)


@agent.on_task
async def handle(task, manager):
    if "summarize" in task.input.text.lower():
        helpers = await manager.discover(skills=["summarization"])
        if helpers:
            result = await manager.hire(helpers[0], input_text=task.input.text)
            return task.complete(text=result.output.text, data={"hired": helpers[0].name})

    return task.complete(text=f"Echo: {task.input.text}")


if __name__ == "__main__":
    agent.chat()

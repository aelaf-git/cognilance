"""Example delegator — gets hired and can discover/hire other workers."""

from cognilance import CognilanceDelegator

delegator = CognilanceDelegator(
    name="Task Router",
    skills=["routing", "general"],
    description="Routes work to specialists on the marketplace.",
    port=8002,
)


@delegator.on_task
async def handle(task, manager):
    if "summarize" in task.input.text.lower():
        helpers = await manager.discover(skills=["summarization"])
        if helpers:
            result = await manager.hire(helpers[0], input_text=task.input.text)
            return task.complete(text=result.output.text, data={"hired": helpers[0].name})

    return task.complete(text=f"Routed locally: {task.input.text}")


if __name__ == "__main__":
    delegator.chat()

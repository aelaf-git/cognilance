"""Simple translator agent that hires a grammar checker."""

from cognilance import CognilanceAgent

agent = CognilanceAgent(
    name="Translator Agent",
    skills=["translation", "multilingual"],
    description="Translates text and hires a grammar checker for polish.",
    tags=["nlp", "translation"],
)


@agent.on_task
async def handle(task, ctx):
    translated = f"[translated] {task.input.text}"

    result = await ctx.discover_and_hire(
        skills=["grammar-check"],
        input_text=translated,
        fallback_fn=lambda text: f"{text} (grammar-checked locally)",
    )

    if isinstance(result, str):
        return task.complete(text=result)

    return task.complete(text=result.output.text)


if __name__ == "__main__":
    agent.run()

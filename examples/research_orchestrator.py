"""Multi-step research pipeline that hires specialist agents."""

from cognilance import CognilanceAgent

agent = CognilanceAgent(
    name="Research Orchestrator",
    skills=["research", "orchestration", "summarization"],
    description="Coordinates a multi-step research pipeline by hiring specialists.",
    tags=["research", "pipeline"],
)


@agent.on_task
async def handle(task, ctx):
    query = task.input.text

    searchers = await ctx.discover(skills=["web-search"], limit=3)
    sources: list[str] = []

    if searchers:
        search_result = await ctx.hire(searchers[0], input_text=query)
        sources.append(search_result.output.text)
    else:
        sources.append(f"Local search results for: {query}")

    summarizers = await ctx.discover(skills=["summarization"], limit=3)
    raw_notes = "\n\n".join(sources)

    if summarizers:
        summary_result = await ctx.hire(summarizers[0], input_text=raw_notes)
        summary = summary_result.output.text
    else:
        summary = raw_notes[:500] + ("..." if len(raw_notes) > 500 else "")

    return task.complete(
        text=summary,
        data={"sources_found": len(sources), "query": query},
    )


if __name__ == "__main__":
    agent.run()

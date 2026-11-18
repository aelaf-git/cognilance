import {
  createActivityState,
  messageForSelection,
  reduceActivityEvent,
  settleActivity
} from "@/lib/coordinator-chat"

describe("activity trace reducer", () => {
  it("accumulates thinking deltas into the thought body", () => {
    let state = createActivityState(1_000)
    state = reduceActivityEvent(state, { event: "thinking", delta: "The user " })
    state = reduceActivityEvent(state, { event: "thinking", delta: "wants a Word file." })

    expect(state.steps[0]).toMatchObject({
      id: "thinking",
      label: "Thinking…",
      detail: "The user wants a Word file."
    })
  })

  it("turns a docx tool start and done into one row that keeps the instruction", () => {
    let state = createActivityState(1_000)
    state = reduceActivityEvent(state, {
      event: "tool_start",
      tool: "docx.create",
      assignee: "docx_agent",
      instruction: '{"title":"The History of Napoleon"}'
    })
    state = reduceActivityEvent(state, {
      event: "tool_done",
      tool: "docx.create",
      assignee: "docx_agent",
      summary: 'Created Word file "The History of Napoleon".'
    })

    const row = state.steps.find(step => step.id.startsWith("tool-"))
    expect(row).toMatchObject({
      label: "Created a Word file",
      prompt: '{"title":"The History of Napoleon"}',
      detail: 'Created Word file "The History of Napoleon".',
      status: "done"
    })
    expect(state.steps.filter(step => step.id.startsWith("tool-"))).toHaveLength(1)
  })

  it("shows the specialist brief on the agent row", () => {
    const state = reduceActivityEvent(createActivityState(1_000), {
      event: "agent_start",
      role: "docx_agent",
      name: "Docx Agent",
      brief: "Goal: Write a short history of Napoleon"
    })

    expect(state.steps.find(step => step.label === "Docx Agent")).toMatchObject({
      prompt: "Goal: Write a short history of Napoleon"
    })
  })

  it("does not invent a wait or a session row for events it does not show", () => {
    let state = createActivityState(1_000)
    state = reduceActivityEvent(state, { event: "session_created", session_type: "chat" })
    state = reduceActivityEvent(state, { event: "mystery_stage" })
    state = reduceActivityEvent(state, {
      event: "tool_start",
      tool: "thinking",
      instruction: "reason quietly"
    })

    expect(state.steps.map(step => step.label)).toEqual(["Thinking…"])
  })

  it("keeps the model thought when a plan event arrives", () => {
    let state = createActivityState(1_000)
    state = reduceActivityEvent(state, { event: "thinking", delta: "The user wants a file." })
    state = reduceActivityEvent(state, {
      event: "plan",
      text: "Write a short rationale the user should not see.",
      data: { reasoning: "Write a short rationale the user should not see." },
      tasks: [{ title: "Draft the file", role: "docx_agent" }]
    })

    expect(state.thinking).toBe("The user wants a file.")
    expect(state.steps.find(step => step.id === "thinking")).toMatchObject({
      detail: "The user wants a file."
    })
    expect(state.steps.find(step => step.id === "plan")).toMatchObject({
      label: "Sketched a plan",
      detail: "Draft the file"
    })
  })

  it("folds the header to Thought Ns when the answer arrives", () => {
    const started = reduceActivityEvent(createActivityState(1_000), {
      event: "thinking",
      delta: "Draft the file."
    })
    const settled = settleActivity(started, 76_400)

    expect(settled.steps[0]).toMatchObject({
      label: "Thought 75s",
      detail: "Draft the file.",
      status: "done"
    })
  })

  it("prefixes a selected block id and leaves other messages alone", () => {
    expect(messageForSelection("Make this shorter.", "blk_ab12cd34")).toBe(
      "Change only block blk_ab12cd34. Leave every other block as it is.\nMake this shorter."
    )
    expect(messageForSelection("Hello", "")).toBe("Hello")
  })
})

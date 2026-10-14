import {
  getConversationId,
  setCognilanceConversation,
  touchCognilance
} from "@/lib/cognilance-store"

const ANSWER_EVENTS = new Set(["direct_reply", "answer_done", "final"])

export type ActivityStep = {
  id: string
  label: string
  detail: string
}

export { clearOrchestratorConversation } from "@/lib/cognilance-store"

function secondsSince(started: number) {
  return Math.max(1, Math.round((Date.now() - started) / 1000))
}

export async function streamOrchestratorReply(
  text: string,
  signal: AbortSignal,
  onText: (text: string) => void,
  onActivity?: (steps: ActivityStep[]) => void
): Promise<void> {
  const conversationId = getConversationId()
  const response = await fetch("/api/chat/cognilance", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    signal,
    body: JSON.stringify({
      text,
      conversation_id: conversationId || undefined
    })
  })

  if (!response.ok || !response.body) {
    let detail = ""
    try {
      const payload = await response.json()
      detail = String(payload.error || payload.detail || "")
    } catch {
      detail = ""
    }
    throw new Error(detail || "Cognilance didn't accept that message.")
  }

  const steps: ActivityStep[] = []
  let thoughtStarted = Date.now()
  let lastMark = Date.now()

  const publish = () => {
    onActivity?.(steps.map(step => ({ ...step })))
  }

  const upsert = (id: string, label: string, detail: string) => {
    const index = steps.findIndex(step => step.id === id)
    const step = { id, label, detail }
    if (index >= 0) steps[index] = step
    else steps.push(step)
    publish()
  }

  const noteWait = () => {
    const gap = Date.now() - lastMark
    lastMark = Date.now()
    if (gap < 2000) return
    steps.push({
      id: `wait-${steps.length}`,
      label: `Waited ${Math.round(gap / 1000)}s`,
      detail: "Paused before continuing."
    })
  }

  const settleThinking = () => {
    const step = steps.find(item => item.id === "thinking")
    if (!step || step.label !== "Thinking…") return
    upsert(
      "thinking",
      `Thought ${secondsSince(thoughtStarted)}s`,
      "Worked through the request before answering."
    )
  }

  upsert("thinking", "Thinking…", "Working through the request.")

  const applyEvent = (event: Record<string, unknown>) => {
    if (event.conversation_id) {
      setCognilanceConversation(String(event.conversation_id))
    }
    const name = String(event.event || "")
    if (!name || ANSWER_EVENTS.has(name)) return
    if (name === "thinking") {
      thoughtStarted = Date.now()
      upsert("thinking", "Thinking…", "Working through the request.")
      return
    }
    noteWait()
    if (name === "thinking_done") {
      upsert(
        "thinking",
        `Thought ${secondsSince(thoughtStarted)}s`,
        "Worked through the request before answering."
      )
      return
    }
    if (name === "session_created") {
      upsert("session", "Opened a session", "This message started its own run.")
      return
    }
    if (name === "plan") {
      upsert("plan", "Sketched a plan", "Lined up the steps before answering.")
      return
    }
    if (name === "route_decision") {
      const route = String(event.route || event.complexity || "")
      if (route === "simple") {
        upsert("route", "Kept it direct", "Answered without a longer process.")
      } else {
        upsert("route", "Split the work", "Broke this into smaller pieces.")
      }
      return
    }
    if (name === "capabilities") {
      upsert("capabilities", "Looked around", "Checked what it could use.")
      return
    }
    if (name === "execution_start") {
      upsert("execution", "Got going", "Started carrying the work out.")
      return
    }
    if (name === "execution_done") {
      upsert("execution-done", "Wrapped up", "The work itself is finished.")
      return
    }
    if (name === "ui") {
      upsert(`ui-${steps.length}`, "Prepared a view", "Put the result into a layout.")
      return
    }
    if (name === "subtask_start") {
      upsert(
        `step-${String(event.id || steps.length)}`,
        "Started a step",
        "Took on one piece of the work."
      )
      return
    }
    if (name === "subtask_done") {
      upsert(
        `step-done-${String(event.id || steps.length)}`,
        "Finished a step",
        "That piece came back."
      )
      return
    }
    if (name === "correction_done") {
      upsert("recheck", "Rechecked", "Looked over the result again.")
    }
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ""
  let answer = ""

  try {
  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    const chunks = buffer.split("\n\n")
    buffer = chunks.pop() ?? ""
    for (const chunk of chunks) {
      const dataLine = chunk
        .split("\n")
        .filter(line => line.startsWith("data:"))
        .map(line => line.slice(5).trim())
        .join("")
      if (!dataLine) continue
      let event: Record<string, unknown>
      try {
        event = JSON.parse(dataLine)
      } catch {
        continue
      }
      const name = String(event.event || "")
      if (name === "error") {
        throw new Error(
          String(event.message || "Cognilance couldn't answer that.")
        )
      }
      applyEvent(event)
      if (
        ANSWER_EVENTS.has(name) &&
        typeof event.text === "string" &&
        event.text
      ) {
        settleThinking()
        answer = event.text
        onText(answer)
      }
    }
  }
  } finally {
    settleThinking()
    touchCognilance()
  }

  if (!answer) {
    throw new Error("Cognilance returned an empty reply.")
  }
}

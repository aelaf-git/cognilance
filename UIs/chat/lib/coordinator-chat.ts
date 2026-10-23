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

function formatPlanThinking(
  data: Record<string, unknown> | undefined,
  fallbackThinking: string
): string {
  if (!data) {
    return fallbackThinking || "Lined up the steps before answering."
  }
  const parts: string[] = []
  const reasoning = String(data.reasoning || data.thinking || "").trim()
  if (reasoning) {
    parts.push(reasoning)
  }
  const planSteps = Array.isArray(data.steps) ? data.steps : []
  for (const raw of planSteps) {
    if (raw && typeof raw === "object") {
      const item = raw as Record<string, unknown>
      const title = String(item.title || "").trim()
      const detail = String(item.detail || "").trim()
      if (title && detail) parts.push(`${title}: ${detail}`)
      else if (title || detail) parts.push(title || detail)
    }
  }
  const subtasks = Array.isArray(data.subtasks) ? data.subtasks : []
  for (const raw of subtasks) {
    if (raw && typeof raw === "object") {
      const sub = raw as Record<string, unknown>
      const title = String(sub.title || "").trim()
      const instruction = String(sub.instruction || "").trim()
      if (title && instruction && title !== instruction) {
        parts.push(`${title}: ${instruction}`)
      } else if (title || instruction) {
        parts.push(title || instruction)
      }
    }
  }
  return parts.join("\n") || fallbackThinking || "Lined up the steps before answering."
}

function formatCapabilitiesThinking(
  rawText: unknown,
  onlineCount: number | null,
  totalCount: number | null
): string {
  const cleaned = String(rawText || "")
    .split("\n")
    .map(line => line.replace(/^===.*===$/, "").trim())
    .filter(Boolean)
    .join(" · ")
  const countNote =
    onlineCount !== null && totalCount !== null
      ? `Checked ${onlineCount}/${totalCount} online agents.`
      : ""
  if (cleaned && countNote) return `${countNote} ${cleaned}`
  if (cleaned) return cleaned
  if (countNote) return countNote
  return "Checked available tools, integrations, and online agents."
}

export async function streamOrchestratorReply(
  text: string,
  signal: AbortSignal,
  onText: (text: string) => void,
  onActivity?: (steps: ActivityStep[]) => void,
  regenerate = false
): Promise<void> {
  const conversationId = getConversationId()
  const response = await fetch("/api/chat/cognilance", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    signal,
    body: JSON.stringify({
      text,
      conversation_id: conversationId || undefined,
      regenerate
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
  let latestThinking = ""
  let onlineAgents: number | null = null
  let totalAgents: number | null = null

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
      detail: "Paused while waiting for the next stage to respond."
    })
  }

  const settleThinking = () => {
    const step = steps.find(item => item.id === "thinking")
    if (!step || step.label !== "Thinking…") return
    upsert(
      "thinking",
      `Thought ${secondsSince(thoughtStarted)}s`,
      latestThinking || "Worked through the request before answering."
    )
  }

  upsert("thinking", "Thinking…", "Working through the request.")

  const applyEvent = (event: Record<string, unknown>) => {
    if (event.conversation_id) {
      const title =
        typeof event.title === "string" && event.title.trim()
          ? event.title.trim()
          : ""
      setCognilanceConversation(String(event.conversation_id), title)
    }
    const name = String(event.event || "")
    if (!name || ANSWER_EVENTS.has(name)) return
    if (name === "thinking" || name === "thinking_done") {
      const textDetail = String(event.text || "").trim()
      if (textDetail) latestThinking = textDetail
      upsert(
        "thinking",
        "Thinking…",
        latestThinking || "Working through the request."
      )
      return
    }
    noteWait()
    if (name === "session_created") {
      const sessionType = String(event.session_type || "chat").replace(/_/g, " ")
      upsert(
        "session",
        "Opened a session",
        `Started a ${sessionType} session for "${text.slice(0, 80)}${text.length > 80 ? "…" : ""}".`
      )
      return
    }
    if (name === "catalog") {
      if (typeof event.online_count === "number") onlineAgents = event.online_count
      if (typeof event.total_count === "number") totalAgents = event.total_count
      return
    }
    if (name === "plan") {
      const planData =
        event.data && typeof event.data === "object"
          ? (event.data as Record<string, unknown>)
          : undefined
      const reasoning = String(planData?.reasoning || planData?.thinking || "").trim()
      if (reasoning) latestThinking = reasoning
      upsert(
        "plan",
        "Sketched a plan",
        formatPlanThinking(planData, latestThinking)
      )
      return
    }
    if (name === "route_decision") {
      const route = String(event.route || event.complexity || "")
      if (route === "simple") {
        upsert(
          "route",
          "Kept it direct",
          latestThinking
            ? `${latestThinking}: answered directly without multi-step delegation.`
            : "Decided this request can be answered directly without extra steps."
        )
      } else {
        upsert(
          "route",
          "Split the work",
          latestThinking
            ? `${latestThinking}: routed through specialized steps.`
            : "Broke the request into smaller specialized pieces."
        )
      }
      return
    }
    if (name === "capabilities") {
      upsert(
        "capabilities",
        "Looked around",
        formatCapabilitiesThinking(event.text, onlineAgents, totalAgents)
      )
      return
    }
    if (name === "execution_start") {
      upsert("execution", "Got going", "Started executing the planned steps.")
      return
    }
    if (name === "execution_done") {
      upsert("execution-done", "Wrapped up", "Finished running all planned steps.")
      return
    }
    if (name === "ui") {
      const uiName = String(event.name || "view")
      upsert(
        `ui-${steps.length}`,
        "Prepared a view",
        `Formatted the output using the ${uiName} layout.`
      )
      return
    }
    if (name === "subtask_start") {
      const title = String(event.title || "").trim()
      const instruction = String(event.instruction || "").trim()
      const assignee = String(event.assignee || "").trim()
      const detailParts = [
        title,
        assignee ? `Assigned to ${assignee}` : "",
        instruction
      ].filter(Boolean)
      upsert(
        `step-${String(event.id || steps.length)}`,
        title ? `Started: ${title}` : "Started a step",
        detailParts.join(". ") || "Took on one piece of the work."
      )
      return
    }
    if (name === "subtask_done") {
      const subText = String(event.text || "").trim()
      upsert(
        `step-done-${String(event.id || steps.length)}`,
        "Finished a step",
        subText || "Completed this step and collected the result."
      )
      return
    }
    if (name === "correction_done") {
      const status = String(event.status || "").trim()
      upsert(
        "recheck",
        "Rechecked",
        status
          ? `Reviewed the output quality (status: ${status}).`
          : "Looked over the result again to verify accuracy."
      )
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

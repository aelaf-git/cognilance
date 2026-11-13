import {
  getConversationId,
  setCognilanceConversation,
  touchCognilance
} from "@/lib/cognilance-store"
import { DocxDocument, parseDocumentEvent } from "@/lib/docx-document"

const ANSWER_EVENTS = new Set(["direct_reply", "answer_done", "final"])
const THINKING_PLACEHOLDER = "Working through the request."
const THINKING_FALLBACK = "Worked through the request before answering."

const TOOL_LABELS: Record<string, [string, string]> = {
  "docx.create": ["Creating a Word file", "Created a Word file"],
  "docx.write": ["Updating the Word file", "Updated the Word file"],
  "docx.style": ["Restyling the Word file", "Restyled the Word file"],
  "docx.read": ["Reading the Word file", "Read the Word file"]
}

export type ActivityStep = {
  id: string
  label: string
  detail: string
  prompt?: string
  status?: "running" | "done"
}

type OpenTool = {
  id: string
  tool: string
  assignee: string
}

export type ActivityState = {
  steps: ActivityStep[]
  thoughtStarted: number
  thinking: string
  toolSeq: number
  openTools: OpenTool[]
  agentSeq: number
  verifySeq: number
  statusSeq: number
  onlineAgents: number | null
  totalAgents: number | null
}

export { clearOrchestratorConversation } from "@/lib/cognilance-store"

function toolLabel(toolId: string, done: boolean): string {
  const pair = TOOL_LABELS[toolId]
  if (pair) return done ? pair[1] : pair[0]
  return toolId
}

function isThinkingTool(toolId: string): boolean {
  return toolId === "thinking" || toolId.startsWith("thinking.")
}

function appendParagraph(current: string, next: string): string {
  const addition = next.trim()
  if (!addition) return current
  if (!current.trim()) return addition
  if (current.includes(addition)) return current
  return `${current.trimEnd()}\n\n${addition}`
}

function upsertStep(steps: ActivityStep[], step: ActivityStep): ActivityStep[] {
  const index = steps.findIndex(item => item.id === step.id)
  if (index < 0) return [...steps, step]
  const next = steps.slice()
  next[index] = step
  return next
}

export function createActivityState(now = Date.now()): ActivityState {
  return {
    steps: [
      {
        id: "thinking",
        label: "Thinking…",
        detail: THINKING_PLACEHOLDER,
        status: "running"
      }
    ],
    thoughtStarted: now,
    thinking: "",
    toolSeq: 0,
    openTools: [],
    agentSeq: 0,
    verifySeq: 0,
    statusSeq: 0,
    onlineAgents: null,
    totalAgents: null
  }
}

function withThinking(state: ActivityState, thinking: string): ActivityState {
  return {
    ...state,
    thinking,
    steps: upsertStep(state.steps, {
      id: "thinking",
      label: "Thinking…",
      detail: thinking.trim() || THINKING_PLACEHOLDER,
      status: "running"
    })
  }
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
  if (reasoning) parts.push(reasoning)
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
      } else if (title || instruction) parts.push(title || instruction)
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

function addAgentRow(
  state: ActivityState,
  name: string,
  prompt: string
): ActivityState {
  const id = `agent-${state.agentSeq}`
  return {
    ...state,
    agentSeq: state.agentSeq + 1,
    steps: upsertStep(state.steps, {
      id,
      label: name || "Agent",
      detail: "",
      prompt: prompt || undefined,
      status: "running"
    })
  }
}

export function settleActivity(state: ActivityState, now = Date.now()): ActivityState {
  const seconds = Math.max(1, Math.round((now - state.thoughtStarted) / 1000))
  const open = new Map(state.openTools.map(item => [item.id, item.tool]))
  return {
    ...state,
    openTools: [],
    steps: state.steps.map(step => {
      if (step.id === "thinking" && step.label === "Thinking…") {
        return {
          ...step,
          label: `Thought ${seconds}s`,
          detail: state.thinking.trim() || THINKING_FALLBACK,
          status: "done"
        }
      }
      if (step.status !== "running") return step
      const tool = open.get(step.id)
      return {
        ...step,
        status: "done",
        label: tool ? toolLabel(tool, true) : step.label
      }
    })
  }
}

export function reduceActivityEvent(
  state: ActivityState,
  event: Record<string, unknown>
): ActivityState {
  const name = String(event.event || "")
  if (!name || ANSWER_EVENTS.has(name)) return state

  if (name === "thinking" || name === "thinking_done") {
    const delta = String(event.delta || "")
    const text = String(event.text || "").trim()
    if (delta) return withThinking(state, state.thinking + delta)
    if (text) return withThinking(state, appendParagraph(state.thinking, text))
    return state
  }

  if (name === "session_created" || name === "document" || name === "ui" || name === "done") {
    return state
  }

  if (name === "catalog") {
    return {
      ...state,
      onlineAgents:
        typeof event.online_count === "number" ? event.online_count : state.onlineAgents,
      totalAgents:
        typeof event.total_count === "number" ? event.total_count : state.totalAgents
    }
  }

  if (name === "agent_start" || name === "specialist_start") {
    const agentName = String(event.name || event.role || "Agent").trim()
    const brief = String(event.brief || "").trim()
    return addAgentRow(state, agentName, brief)
  }

  if (name === "specialist_done") {
    const agentName = String(event.name || event.role || "").trim()
    return {
      ...state,
      steps: state.steps.map(step => {
        if (step.status !== "running" || !step.id.startsWith("agent-")) return step
        if (agentName && step.label !== agentName && step.label !== String(event.role || "")) {
          return step
        }
        return { ...step, status: "done" }
      })
    }
  }

  if (name === "tool_start" || name === "tool_done") {
    const tool = String(event.tool || "").trim()
    if (!tool || isThinkingTool(tool)) return state
    const assignee = String(event.assignee || "").trim()
    if (name === "tool_start") {
      const id = `tool-${state.toolSeq}`
      const instruction = String(event.instruction || "").trim()
      return {
        ...state,
        toolSeq: state.toolSeq + 1,
        openTools: [...state.openTools, { id, tool, assignee }],
        steps: upsertStep(state.steps, {
          id,
          label: toolLabel(tool, false),
          detail: "",
          prompt: instruction || undefined,
          status: "running"
        })
      }
    }
    const openIndex = state.openTools.findIndex(
      item => item.tool === tool && item.assignee === assignee
    )
    const summary = String(event.summary || "").trim()
    if (openIndex < 0) {
      const id = `tool-${state.toolSeq}`
      return {
        ...state,
        toolSeq: state.toolSeq + 1,
        steps: upsertStep(state.steps, {
          id,
          label: toolLabel(tool, true),
          detail: summary,
          status: "done"
        })
      }
    }
    const open = state.openTools[openIndex]
    const existing = state.steps.find(step => step.id === open.id)
    return {
      ...state,
      openTools: state.openTools.filter((_, index) => index !== openIndex),
      steps: upsertStep(state.steps, {
        id: open.id,
        label: toolLabel(tool, true),
        detail: summary,
        prompt: existing?.prompt,
        status: "done"
      })
    }
  }

  if (name === "status") {
    const message = String(event.message || "").trim()
    if (!message) return state
    const previous = [...state.steps].reverse().find(step => step.id.startsWith("status-"))
    if (previous?.label === message) return state
    const id = `status-${state.statusSeq}`
    return {
      ...state,
      statusSeq: state.statusSeq + 1,
      steps: upsertStep(state.steps, {
        id,
        label: message,
        detail: "",
        status: "done"
      })
    }
  }

  if (name === "verify") {
    const passed = event.passed !== false
    const reason = String(event.reasoning || event.reason || "").trim()
    const issues = Array.isArray(event.issues)
      ? event.issues.map(item => String(item).trim()).filter(Boolean)
      : []
    const id = `verify-${state.verifySeq}`
    return {
      ...state,
      verifySeq: state.verifySeq + 1,
      steps: upsertStep(state.steps, {
        id,
        label: passed ? "Checked the result" : "Needs another look",
        detail: [reason, ...issues].filter(Boolean).join("\n"),
        status: "done"
      })
    }
  }

  if (name === "approval_required") {
    const tool = String(event.tool || "a tool").trim()
    const risk = String(event.risk || "").trim()
    return {
      ...state,
      steps: upsertStep(state.steps, {
        id: "approval",
        label: "Waiting for approval",
        detail: risk ? `${tool} · risk ${risk}` : tool,
        status: "running"
      })
    }
  }

  if (name === "plan") {
    const planData =
      event.data && typeof event.data === "object"
        ? (event.data as Record<string, unknown>)
        : undefined
    const reasoning = String(
      planData?.reasoning || planData?.thinking || event.text || ""
    ).trim()
    const next = reasoning ? withThinking(state, appendParagraph(state.thinking, reasoning)) : state
    return {
      ...next,
      steps: upsertStep(next.steps, {
        id: "plan",
        label: "Sketched a plan",
        detail: formatPlanThinking(planData, next.thinking),
        status: "done"
      })
    }
  }

  if (name === "route_decision") {
    const route = String(event.route || event.complexity || "")
    const direct = route === "simple"
    return {
      ...state,
      steps: upsertStep(state.steps, {
        id: "route",
        label: direct ? "Kept it direct" : "Split the work",
        detail: state.thinking
          ? `${state.thinking}: ${
              direct
                ? "answered directly without multi-step delegation."
                : "routed through specialized steps."
            }`
          : direct
            ? "Decided this request can be answered directly without extra steps."
            : "Broke the request into smaller specialized pieces.",
        status: "done"
      })
    }
  }

  if (name === "capabilities") {
    return {
      ...state,
      steps: upsertStep(state.steps, {
        id: "capabilities",
        label: "Looked around",
        detail: formatCapabilitiesThinking(
          event.text,
          state.onlineAgents,
          state.totalAgents
        ),
        status: "done"
      })
    }
  }

  if (name === "execution_start") {
    return {
      ...state,
      steps: upsertStep(state.steps, {
        id: "execution",
        label: "Got going",
        detail: "Started executing the planned steps.",
        status: "running"
      })
    }
  }

  if (name === "execution_done") {
    return {
      ...state,
      steps: upsertStep(state.steps, {
        id: "execution-done",
        label: "Wrapped up",
        detail: "Finished running all planned steps.",
        status: "done"
      })
    }
  }

  if (name === "subtask_start") {
    const title = String(event.title || "").trim()
    const instruction = String(event.instruction || "").trim()
    const assignee = String(event.assignee || "").trim()
    return {
      ...state,
      steps: upsertStep(state.steps, {
        id: `step-${String(event.id || state.steps.length)}`,
        label: title || "Started a step",
        detail: assignee ? `Assigned to ${assignee}` : "",
        prompt: instruction || undefined,
        status: "running"
      })
    }
  }

  if (name === "subtask_done") {
    const subText = String(event.text || "").trim()
    return {
      ...state,
      steps: upsertStep(state.steps, {
        id: `step-done-${String(event.id || state.steps.length)}`,
        label: "Finished a step",
        detail: subText || "Completed this step and collected the result.",
        status: "done"
      })
    }
  }

  if (name === "correction_done") {
    const status = String(event.status || "").trim()
    return {
      ...state,
      steps: upsertStep(state.steps, {
        id: "recheck",
        label: "Rechecked",
        detail: status
          ? `Reviewed the output quality (status: ${status}).`
          : "Looked over the result again to verify accuracy.",
        status: "done"
      })
    }
  }

  return state
}

export async function streamOrchestratorReply(
  text: string,
  signal: AbortSignal,
  onText: (text: string) => void,
  onActivity?: (steps: ActivityStep[]) => void,
  onDocument?: (document: DocxDocument) => void,
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

  let activity = createActivityState()
  const publish = () => {
    onActivity?.(activity.steps.map(step => ({ ...step })))
  }
  publish()

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
        if (event.conversation_id) {
          const title =
            typeof event.title === "string" && event.title.trim()
              ? event.title.trim()
              : ""
          setCognilanceConversation(String(event.conversation_id), title)
        }
        const name = String(event.event || "")
        if (name === "error") {
          throw new Error(String(event.message || "Cognilance couldn't answer that."))
        }
        if (name === "document") {
          const snapshot = parseDocumentEvent(event)
          if (snapshot) onDocument?.(snapshot)
        }
        activity = reduceActivityEvent(activity, event)
        publish()
        if (ANSWER_EVENTS.has(name) && typeof event.text === "string" && event.text) {
          activity = settleActivity(activity)
          publish()
          answer = event.text
          onText(answer)
        }
      }
    }
  } finally {
    activity = settleActivity(activity)
    publish()
    touchCognilance()
  }

  if (!answer) {
    throw new Error("Cognilance returned an empty reply.")
  }
}

export type CognilanceSnapshot = {
  id: string
  title: string
  revision: number
}

const EMPTY: CognilanceSnapshot = { id: "", title: "", revision: 0 }
const CONVERSATION_KEY = "cognilance_chat_conversation"

let current: CognilanceSnapshot = EMPTY
const listeners = new Set<() => void>()

function emit(next: CognilanceSnapshot) {
  current = next
  listeners.forEach(listener => listener())
}

export function subscribeCognilance(listener: () => void) {
  listeners.add(listener)
  return () => listeners.delete(listener)
}

export function getCognilanceSnapshot() {
  return current
}

export function getCognilanceServerSnapshot() {
  return EMPTY
}

export function getConversationId() {
  if (current.id) return current.id
  try {
    return localStorage.getItem(CONVERSATION_KEY) || ""
  } catch {
    return ""
  }
}

export function setCognilanceConversation(id: string, title = "") {
  try {
    if (id) localStorage.setItem(CONVERSATION_KEY, id)
    else localStorage.removeItem(CONVERSATION_KEY)
  } catch {
    /* storage can be unavailable */
  }
  const nextTitle = title || (id && id === current.id ? current.title : "")
  if (current.id === id && current.title === nextTitle) return
  emit({
    id,
    title: nextTitle,
    revision: current.revision + 1
  })
}

export function touchCognilance() {
  emit({ ...current, revision: current.revision + 1 })
}

export function clearOrchestratorConversation() {
  setCognilanceConversation("", "")
}

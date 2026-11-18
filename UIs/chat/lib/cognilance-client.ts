import { DocxDocument, parseDocumentEvent } from "@/lib/docx-document"
import { ChatMessage, LLMID } from "@/types"

export async function cognilanceJson(path: string, init?: RequestInit) {
  const response = await fetch(`/api/cognilance/${path}`, init)
  const payload = await response.json().catch(() => ({}))
  if (!response.ok) {
    const detail = String(payload.error || payload.detail || "Request failed")
    if (response.status === 401) {
      throw new Error("Sign in to continue.")
    }
    throw new Error(detail)
  }
  return payload
}

export function toChatMessages(
  messages: {
    id: number | string
    role: string
    content: string
    created_at: string
  }[],
  conversationId: string
): ChatMessage[] {
  return messages.map((item, index) => ({
    message: {
      chat_id: conversationId,
      assistant_id: null,
      content: item.content,
      created_at: item.created_at,
      id: String(item.id),
      image_paths: [],
      model: "gpt-4-turbo-preview" as LLMID,
      role: item.role === "assistant" ? "assistant" : "user",
      sequence_number: index,
      updated_at: item.created_at,
      user_id: ""
    },
    fileItems: []
  }))
}

export function withActiveDocument(
  messages: ChatMessage[],
  document: DocxDocument | null
): ChatMessage[] {
  if (!document) return messages
  let index = -1
  for (let i = messages.length - 1; i >= 0; i -= 1) {
    if (messages[i].message.role === "assistant") {
      index = i
      break
    }
  }
  if (index < 0) return messages
  return messages.map((item, itemIndex) =>
    itemIndex === index ? { ...item, document } : item
  )
}

export async function fetchDocxDocument(id: string): Promise<DocxDocument | null> {
  if (!/^doc_[a-f0-9]{12}$/.test(id)) return null
  const response = await fetch(`/api/docx/${id}/content`, { cache: "no-store" })
  if (!response.ok) return null
  const payload = await response.json().catch(() => null)
  if (!payload || typeof payload !== "object") return null
  return parseDocumentEvent(payload as Record<string, unknown>)
}

import { ChatMessage, LLMID } from "@/types"

export async function cognilanceJson(path: string, init?: RequestInit) {
  const response = await fetch(`/api/cognilance/${path}`, init)
  const payload = await response.json().catch(() => ({}))
  if (!response.ok) {
    throw new Error(String(payload.error || payload.detail || "Request failed"))
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

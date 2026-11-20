import { useChatHandler } from "@/components/chat/chat-hooks/use-chat-handler"
import { ChatbotUIContext } from "@/context/context"
import { cognilanceJson, MESSAGE_PAGE, toChatMessages } from "@/lib/cognilance-client"
import {
  getCognilanceServerSnapshot,
  getCognilanceSnapshot,
  setHasEarlier,
  subscribeCognilance
} from "@/lib/cognilance-store"
import { Tables } from "@/supabase/types"
import { FC, useContext, useState, useSyncExternalStore } from "react"
import { Message } from "../messages/message"

interface ChatMessagesProps {}

export const ChatMessages: FC<ChatMessagesProps> = ({}) => {
  const { chatMessages, chatFileItems, setChatMessages } = useContext(ChatbotUIContext)
  const snapshot = useSyncExternalStore(
    subscribeCognilance,
    getCognilanceSnapshot,
    getCognilanceServerSnapshot
  )

  const { handleSendEdit } = useChatHandler()

  const [editingMessage, setEditingMessage] = useState<Tables<"messages">>()
  const [loadingEarlier, setLoadingEarlier] = useState(false)

  const loadEarlier = async () => {
    const conversationId = snapshot.id
    const oldest = [...chatMessages].sort(
      (a, b) => a.message.sequence_number - b.message.sequence_number
    )[0]
    if (!conversationId || !oldest || loadingEarlier) return
    setLoadingEarlier(true)
    try {
      const payload = await cognilanceJson(
        `conversations/${conversationId}?before=${encodeURIComponent(oldest.message.id)}`
      )
      const older = toChatMessages(payload.messages || [], conversationId)
      setHasEarlier((payload.messages || []).length >= MESSAGE_PAGE)
      setChatMessages(current => {
        const seen = new Set(current.map(item => item.message.id))
        const fresh = older.filter(item => !seen.has(item.message.id))
        const start = current.reduce(
          (min, item) => Math.min(min, item.message.sequence_number),
          0
        )
        const olderSequenced = fresh.map((item, index) => ({
          ...item,
          message: {
            ...item.message,
            sequence_number: start - fresh.length + index
          }
        }))
        return [...olderSequenced, ...current]
      })
    } catch {
      /* Leave the control in place so the request can be retried. */
    } finally {
      setLoadingEarlier(false)
    }
  }

  const ordered = [...chatMessages].sort(
    (a, b) => a.message.sequence_number - b.message.sequence_number
  )

  return (
    <>
      {snapshot.hasEarlier && snapshot.id ? (
        <div className="flex justify-center py-3">
          <button
            type="button"
            className="text-xs text-muted-foreground hover:text-foreground disabled:opacity-50"
            onClick={loadEarlier}
            disabled={loadingEarlier}
          >
            {loadingEarlier ? "Loading…" : "Earlier messages"}
          </button>
        </div>
      ) : null}
      {ordered.map((chatMessage, index, array) => {
        const messageFileItems = chatFileItems.filter(
          (chatFileItem, _, self) =>
            chatMessage.fileItems.includes(chatFileItem.id) &&
            self.findIndex(item => item.id === chatFileItem.id) === _
        )

        return (
          <Message
            key={chatMessage.message.sequence_number}
            message={chatMessage.message}
            fileItems={messageFileItems}
            activity={chatMessage.activity}
            docx={chatMessage.document}
            authorName={chatMessage.authorName}
            isEditing={editingMessage?.id === chatMessage.message.id}
            isLast={index === array.length - 1}
            onStartEdit={setEditingMessage}
            onCancelEdit={() => setEditingMessage(undefined)}
            onSubmitEdit={handleSendEdit}
          />
        )
      })}
    </>
  )
}

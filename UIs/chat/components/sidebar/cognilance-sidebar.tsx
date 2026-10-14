"use client"

import { ChatbotUIContext } from "@/context/context"
import { cognilanceJson, toChatMessages } from "@/lib/cognilance-client"
import {
  getCognilanceServerSnapshot,
  getCognilanceSnapshot,
  getConversationId,
  setCognilanceConversation,
  subscribeCognilance
} from "@/lib/cognilance-store"
import { cn } from "@/lib/utils"
import { IconPlugConnected, IconPlus } from "@tabler/icons-react"
import { useRouter } from "next/navigation"
import { FC, useContext, useEffect, useState, useSyncExternalStore } from "react"

type ConversationItem = {
  id: string
  title: string
  session_count?: number
  latest_status?: string | null
}

type SessionItem = {
  id: string
  instruction: string
  session_type?: string
  display_status?: string
  status?: string
}

type IntegrationItem = {
  id: string
  name: string
  description?: string
  connected?: boolean
  coming_soon?: boolean
}

function statusLabel(session: SessionItem) {
  const status = session.display_status || session.status || ""
  if (status === "processing" || status === "running" || status === "queued") {
    return "Running"
  }
  if (status === "done" || status === "completed") return "Done"
  if (status === "failed") return "Failed"
  if (status === "aborted" || status === "cancelled") return "Stopped"
  return status || "Done"
}

export const CognilanceSidebar: FC<{ contentType: string }> = ({
  contentType
}) => {
  const router = useRouter()
  const snapshot = useSyncExternalStore(
    subscribeCognilance,
    getCognilanceSnapshot,
    getCognilanceServerSnapshot
  )
  const { setChatMessages, setUserInput, chatMessages } = useContext(ChatbotUIContext)

  useEffect(() => {
    const storedId = getConversationId()
    if (storedId && !getCognilanceSnapshot().id) {
      setCognilanceConversation(storedId)
    }
  }, [])

  useEffect(() => {
    const id = snapshot.id
    if (!id || chatMessages.length > 0) return
    let cancelled = false
    cognilanceJson(`conversations/${id}`)
      .then(payload => {
        if (cancelled) return
        setChatMessages(current =>
          current.length > 0
            ? current
            : toChatMessages(payload.messages || [], id)
        )
        if (payload.title) setCognilanceConversation(id, payload.title)
      })
      .catch(() => {})
    return () => {
      cancelled = true
    }
  }, [snapshot.id, chatMessages.length, setChatMessages])
  const [conversations, setConversations] = useState<ConversationItem[]>([])
  const [sessions, setSessions] = useState<SessionItem[]>([])
  const [integrations, setIntegrations] = useState<IntegrationItem[]>([])
  const [error, setError] = useState("")
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    let cancelled = false
    const load = async () => {
      setLoading(true)
      setError("")
      try {
        if (contentType === "sessions") {
          const id = snapshot.id
          if (!id) {
            if (!cancelled) setSessions([])
            return
          }
          const payload = await cognilanceJson(`conversations/${id}/sessions`)
          if (!cancelled) setSessions(payload.sessions || [])
          return
        }
        if (contentType === "integrations") {
          const payload = await cognilanceJson("integrations/list")
          if (!cancelled) {
            setIntegrations(payload.integrations || payload.apps || [])
          }
          return
        }
        const payload = await cognilanceJson("conversations")
        if (!cancelled) {
          const items = payload.conversations || []
          setConversations(items)
          const open = items.find(
            (item: ConversationItem) => item.id === snapshot.id
          )
          if (open?.title) setCognilanceConversation(open.id, open.title)
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Couldn't load that.")
        }
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    load()
    return () => {
      cancelled = true
    }
  }, [contentType, snapshot.id, snapshot.revision])

  const openConversation = async (item: ConversationItem) => {
    setCognilanceConversation(item.id, item.title)
    setUserInput("")
    try {
      const payload = await cognilanceJson(`conversations/${item.id}`)
      setChatMessages(toChatMessages(payload.messages || [], item.id))
      if (payload.title) setCognilanceConversation(item.id, payload.title)
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't open that conversation.")
    }
    if (!window.location.pathname.endsWith("/chat")) {
      router.push("/local/chat")
    }
  }

  const startConversation = () => {
    setCognilanceConversation("", "")
    setChatMessages([])
    setUserInput("")
    router.push("/local/chat")
  }

  if (contentType === "integrations") {
    return (
      <Panel title="Integrations" loading={loading} error={error}>
        {integrations.map(item => (
          <div key={item.id} className="border-border border-b py-3">
            <div className="flex items-center justify-between gap-2">
              <div className="font-medium">{item.name}</div>
              <IconPlugConnected size={16} className="text-muted-foreground" />
            </div>
            {item.description && (
              <div className="text-muted-foreground mt-1 text-xs">
                {item.description}
              </div>
            )}
            <div className="mt-2">
              {item.coming_soon ? (
                <span className="text-muted-foreground text-xs">Coming soon</span>
              ) : item.connected ? (
                <button
                  type="button"
                  className="text-xs text-primary"
                  onClick={async () => {
                    await cognilanceJson(`integrations/${item.id}/disconnect`, {
                      method: "POST"
                    })
                    setIntegrations(current =>
                      current.map(entry =>
                        entry.id === item.id
                          ? { ...entry, connected: false }
                          : entry
                      )
                    )
                  }}
                >
                  Connected
                </button>
              ) : (
                <a
                  className="text-xs text-primary"
                  href={`/api/cognilance/integrations/${item.id}/connect`}
                >
                  Connect
                </a>
              )}
            </div>
          </div>
        ))}
      </Panel>
    )
  }

  if (contentType === "sessions") {
    const short = sessions.filter(item => item.session_type !== "recurring")
    const long = sessions.filter(item => item.session_type === "recurring")
    return (
      <Panel title="Sessions" loading={loading} error={error}>
        {!snapshot.id ? (
          <p className="text-muted-foreground text-sm">
            Open a conversation to see its sessions.
          </p>
        ) : (
          <>
            <p className="text-muted-foreground mb-3 text-xs">
              Runs inside {snapshot.title || "this conversation"}
            </p>
            <SessionGroup title="Short" sessions={short} />
            <SessionGroup title="Long running" sessions={long} />
          </>
        )}
      </Panel>
    )
  }

  return (
    <Panel
      title="Conversations"
      loading={loading}
      error={error}
      action={
        <button
          type="button"
          className="text-muted-foreground hover:text-foreground"
          onClick={startConversation}
          aria-label="New conversation"
        >
          <IconPlus size={18} />
        </button>
      }
    >
      {conversations.length === 0 && !loading && (
        <p className="text-muted-foreground text-sm">No conversations yet.</p>
      )}
      {conversations.map(item => (
        <button
          key={item.id}
          type="button"
          onClick={() => openConversation(item)}
          className={cn(
            "hover:bg-muted w-full rounded-md px-2 py-2 text-left",
            snapshot.id === item.id && "bg-muted"
          )}
        >
          <div className="truncate text-sm">{item.title || "Conversation"}</div>
          <div className="text-muted-foreground text-xs">
            {item.session_count || 0}{" "}
            {(item.session_count || 0) === 1 ? "session" : "sessions"}
          </div>
        </button>
      ))}
    </Panel>
  )
}

const Panel: FC<{
  title: string
  loading: boolean
  error: string
  action?: React.ReactNode
  children: React.ReactNode
}> = ({ title, loading, error, action, children }) => (
  <div className="flex h-full min-h-0 flex-col">
    <div className="mb-3 flex items-center justify-between">
      <div className="text-lg font-semibold">{title}</div>
      {action}
    </div>
    {error && <p className="text-destructive mb-2 text-xs">{error}</p>}
    <div className="min-h-0 flex-1 space-y-1 overflow-y-auto">
      {loading ? <p className="text-muted-foreground text-sm">Loading…</p> : children}
    </div>
  </div>
)

const SessionGroup: FC<{ title: string; sessions: SessionItem[] }> = ({
  title,
  sessions
}) => (
  <div className="mb-4">
    <div className="text-muted-foreground mb-1 text-xs uppercase tracking-wide">
      {title}
    </div>
    {sessions.length === 0 ? (
      <p className="text-muted-foreground text-sm">None</p>
    ) : (
      sessions.map(session => (
        <div key={session.id} className="py-2">
          <div className="line-clamp-2 text-sm">
            {session.instruction || "Session"}
          </div>
          <div className="text-muted-foreground text-xs">{statusLabel(session)}</div>
        </div>
      ))
    )}
  </div>
)

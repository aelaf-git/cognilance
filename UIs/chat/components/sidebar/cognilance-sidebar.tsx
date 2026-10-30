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
import { IconPlugConnected, IconPlus, IconTrash } from "@tabler/icons-react"
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
  listener_active?: boolean
  subscription_id?: string | null
  listener_kind?: string | null
  listener_integration?: string | null
}

const rowDelay = (index: number) => ({
  animationDelay: `${Math.min(index, 8) * 30}ms`
})

type IntegrationItem = {
  id: string
  name: string
  description?: string
  logo?: string
  connected?: boolean
  coming_soon?: boolean
}

function isLongRunningSession(session: SessionItem) {
  return (
    session.session_type === "recurring" ||
    !!session.listener_active ||
    !!session.subscription_id
  )
}

function isSessionRunning(session: SessionItem) {
  if (session.listener_active) return true
  const status = session.display_status || session.status || ""
  return (
    status === "processing" || status === "running" || status === "queued"
  )
}

function statusLabel(session: SessionItem) {
  if (isSessionRunning(session)) return "Running"
  const status = session.display_status || session.status || ""
  if (status === "done" || status === "completed") return "Done"
  if (status === "failed") return "Failed"
  if (status === "aborted" || status === "cancelled") return "Stopped"
  return status || "Stopped"
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
  const { setChatMessages, setUserInput, chatMessages } =
    useContext(ChatbotUIContext)

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

  const startConversation = async () => {
    setError("")
    try {
      const created = await cognilanceJson("conversations", { method: "POST" })
      const item: ConversationItem = {
        id: created.id,
        title: created.title || "New conversation",
        session_count: created.session_count || 0,
        latest_status: created.latest_status ?? null
      }
      setConversations(current => [
        item,
        ...current.filter(entry => entry.id !== item.id)
      ])
      setCognilanceConversation(item.id, item.title)
      setChatMessages([])
      setUserInput("")
      if (!window.location.pathname.endsWith("/chat")) {
        router.push("/local/chat")
      }
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Couldn't create a conversation."
      )
    }
  }

  const deleteConversation = async (item: ConversationItem) => {
    setError("")
    try {
      await cognilanceJson(`conversations/${item.id}`, { method: "DELETE" })
      const remaining = conversations.filter(entry => entry.id !== item.id)
      setConversations(remaining)
      if (snapshot.id === item.id) {
        if (remaining[0]) {
          await openConversation(remaining[0])
        } else {
          setCognilanceConversation("", "")
          setChatMessages([])
          setUserInput("")
        }
      }
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Couldn't delete that conversation."
      )
    }
  }

  if (contentType === "integrations") {
    return (
      <Panel title="Integrations" loading={loading} error={error}>
        <div className="space-y-0.5">
          {integrations.map((item, index) => {
            const logoKey = item.logo || item.id
            const isGithub = logoKey === "github" || item.id === "github"
            const isMonochromeSvg =
              isGithub ||
              logoKey === "x" ||
              logoKey === "reddit" ||
              logoKey === "linkedin"
            return (
              <div
                key={item.id}
                className="chat-row flex items-center justify-between gap-3 rounded-lg px-2 py-2 transition-colors hover:bg-accent/70"
                style={rowDelay(index)}
              >
                <div className="flex min-w-0 items-center gap-3">
                  <div className="flex size-8 shrink-0 items-center justify-center overflow-hidden rounded-lg border border-border/80 bg-[hsl(var(--chat-canvas))]">
                    <img
                      src={
                        isGithub
                          ? "/integrations/github.svg"
                          : `/api/cognilance/integrations/logos/${encodeURIComponent(logoKey)}`
                      }
                      alt=""
                      className={cn(
                        "size-5 object-contain",
                        isMonochromeSvg && "dark:invert"
                      )}
                      onError={event => {
                        event.currentTarget.style.display = "none"
                        const fallback = event.currentTarget.nextElementSibling
                        if (fallback instanceof HTMLElement) {
                          fallback.style.display = "block"
                        }
                      }}
                    />
                    <IconPlugConnected
                      size={16}
                      className="text-muted-foreground hidden"
                    />
                  </div>
                  <div className="font-[family-name:var(--font-display)] min-w-0 truncate text-[13.5px] font-medium tracking-tight text-foreground">
                    {item.name}
                  </div>
                </div>
                <div className="shrink-0">
                  {item.coming_soon ? (
                    <span className="font-[family-name:var(--font-display)] rounded-md border border-border/60 bg-[hsl(var(--chat-canvas))] px-2 py-0.5 text-[10px] font-medium uppercase tracking-[0.08em] text-muted-foreground">
                      Soon
                    </span>
                  ) : item.connected ? (
                    <div className="flex items-center gap-2">
                      <span className="inline-flex items-center gap-1.5 text-[11px] font-medium text-foreground">
                        <span className="size-1.5 rounded-full bg-foreground" />
                        Connected
                      </span>
                      <button
                        type="button"
                        className="rounded-md border border-border bg-[hsl(var(--chat-canvas))] px-2 py-1 text-[11px] font-medium text-muted-foreground transition-colors hover:border-foreground hover:text-foreground"
                        onClick={async () => {
                          await cognilanceJson(
                            `integrations/${item.id}/disconnect`,
                            { method: "POST" }
                          )
                          setIntegrations(current =>
                            current.map(entry =>
                              entry.id === item.id
                                ? { ...entry, connected: false }
                                : entry
                            )
                          )
                        }}
                      >
                        Disconnect
                      </button>
                    </div>
                  ) : (
                    <a
                      className="inline-flex items-center rounded-md border border-border bg-[hsl(var(--chat-canvas))] px-2.5 py-1 text-xs font-medium text-foreground transition-colors hover:border-foreground hover:bg-foreground hover:text-background"
                      href={`/api/cognilance/integrations/${item.id}/connect`}
                    >
                      Connect
                    </a>
                  )}
                </div>
              </div>
            )
          })}
        </div>
      </Panel>
    )
  }

  if (contentType === "sessions") {
    const longRunning = sessions.filter(isLongRunningSession)

    const refreshSessions = async () => {
      const id = snapshot.id
      if (!id) return
      const payload = await cognilanceJson(`conversations/${id}/sessions`)
      setSessions(payload.sessions || [])
    }

    const stopSession = async (session: SessionItem) => {
      try {
        await cognilanceJson(`sessions/${session.id}/abort`, { method: "POST" })
        await refreshSessions()
      } catch (err) {
        setError(err instanceof Error ? err.message : "Couldn't stop that session.")
      }
    }

    const startSession = async (session: SessionItem) => {
      try {
        await cognilanceJson(`sessions/${session.id}/start`, { method: "POST" })
        await refreshSessions()
      } catch (err) {
        setError(
          err instanceof Error ? err.message : "Couldn't start that session."
        )
      }
    }

    return (
      <Panel title="Sessions" loading={loading} error={error}>
        {!snapshot.id ? (
          <p className="text-muted-foreground text-sm">
            Open a conversation to see its background sessions.
          </p>
        ) : (
          <>
            <p className="text-muted-foreground mb-3 text-xs">
              Long-running background tasks for{" "}
              {snapshot.title || "this conversation"}
            </p>
            {longRunning.length === 0 ? (
              <p className="text-muted-foreground text-sm">
                No background sessions yet.
              </p>
            ) : (
              longRunning.map((session, index) => {
                const running = isSessionRunning(session)
                return (
                  <div
                    key={session.id}
                    className="chat-row mb-2 flex items-start justify-between gap-2 rounded-[12px] border border-border bg-[hsl(var(--chat-surface))] p-3 transition-colors hover:bg-accent"
                    style={rowDelay(index)}
                  >
                    <div className="min-w-0 flex-1">
                      <div className="line-clamp-2 text-sm">
                        {session.instruction || "Background session"}
                      </div>
                      <div className="mt-1 text-xs text-muted-foreground">
                        <span
                          className={cn(
                            (session.display_status || session.status) ===
                              "failed" && "text-destructive",
                            isSessionRunning(session) && "text-foreground"
                          )}
                        >
                          {statusLabel(session)}
                        </span>
                        {session.listener_integration
                          ? ` · ${session.listener_integration}`
                          : ""}
                      </div>
                    </div>
                    <button
                      type="button"
                      className={cn(
                        "shrink-0 rounded-[6px] px-2 py-1 text-xs font-medium underline-offset-2 hover:underline",
                        running
                          ? "text-destructive"
                          : "text-foreground"
                      )}
                      onClick={() =>
                        void (running
                          ? stopSession(session)
                          : startSession(session))
                      }
                      disabled={!running && !session.subscription_id}
                    >
                      {running ? "Stop" : "Start"}
                    </button>
                  </div>
                )
              })
            )}
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
          className="flex size-7 items-center justify-center rounded-md border border-border bg-[hsl(var(--chat-canvas))] text-muted-foreground transition-colors hover:border-foreground hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          onClick={() => void startConversation()}
          aria-label="New conversation"
        >
          <IconPlus size={15} stroke={2} />
        </button>
      }
    >
      {conversations.length === 0 && !loading && (
        <p className="text-muted-foreground px-2 py-2 text-xs">
          No conversations yet.
        </p>
      )}
      <div className="space-y-0.5">
        {conversations.map((item, index) => (
          <div
            key={item.id}
            className={cn(
              "chat-row group flex w-full items-center gap-1 rounded-lg px-2.5 py-2 transition-colors hover:bg-accent/70",
              snapshot.id === item.id &&
                "bg-accent font-medium text-foreground"
            )}
            style={rowDelay(index)}
          >
            <button
              type="button"
              onClick={() => openConversation(item)}
              className="min-w-0 flex-1 text-left"
            >
              <div className="truncate text-[13.5px]">
                {item.title || "New conversation"}
              </div>
            </button>
            <button
              type="button"
              className="text-muted-foreground hover:text-destructive shrink-0 rounded-md p-1 opacity-0 transition-opacity hover:bg-background/60 group-hover:opacity-100"
              aria-label={`Delete ${item.title || "conversation"}`}
              onClick={event => {
                event.stopPropagation()
                void deleteConversation(item)
              }}
            >
              <IconTrash size={14} />
            </button>
          </div>
        ))}
      </div>
    </Panel>
  )
}

const Panel: FC<{
  title: string
  eyebrow?: string
  lead?: string
  loading: boolean
  error: string
  action?: React.ReactNode
  children: React.ReactNode
}> = ({ title, eyebrow, lead, loading, error, action, children }) => (
  <div className="flex h-full min-h-0 flex-col px-1">
    <div className="mb-2 border-b border-border/70 px-2 pb-3">
      <div className="flex items-center justify-between gap-2">
        <div className="min-w-0">
          {eyebrow && (
            <p className="font-[family-name:var(--font-display)] mb-0.5 text-[10px] font-semibold uppercase tracking-[0.14em] text-muted-foreground">
              {eyebrow}
            </p>
          )}
          <div className="font-[family-name:var(--font-display)] text-[15px] font-semibold tracking-tight text-foreground">
            {title}
          </div>
          {lead && (
            <p className="text-muted-foreground mt-1 text-xs leading-5">
              {lead}
            </p>
          )}
        </div>
        {action}
      </div>
    </div>
    {error && <p className="text-destructive mb-2 px-2 text-xs">{error}</p>}
    <div className="sidebar-panel-scroll min-h-0 flex-1 overflow-y-auto">
      {loading ? (
        <p className="text-muted-foreground px-2 py-2 text-xs">Loading…</p>
      ) : (
        children
      )}
    </div>
  </div>
)

"use client"

import { ChatbotUIContext } from "@/context/context"
import { watchSharedConversation, stopSharedConversation } from "@/lib/coordinator-chat"
import {
  cognilanceJson,
  fetchDocxDocument,
  MESSAGE_PAGE,
  toChatMessages,
  withActiveDocument
} from "@/lib/cognilance-client"
import {
  clearOrchestratorConversation,
  getCognilanceServerSnapshot,
  getCognilanceSnapshot,
  getConversationId,
  setCognilanceConversation,
  setHasEarlier,
  subscribeCognilance
} from "@/lib/cognilance-store"
import { cn } from "@/lib/utils"
import {
  IconChevronLeft,
  IconChevronRight,
  IconLogout,
  IconPlugConnected,
  IconPlus,
  IconTrash
} from "@tabler/icons-react"
import { useTheme } from "next-themes"
import Link from "next/link"
import { useRouter } from "next/navigation"
import { FC, FormEvent, useContext, useEffect, useRef, useState, useSyncExternalStore } from "react"

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

type AlertLink = {
  type?: string
  task_id?: string
  project_id?: string
  conversation_id?: string
  run_id?: string
  url?: string
}

type AlertItem = {
  id: string
  summary: string
  kind: string
  priority?: string
  assignee_account_id?: string | null
  read?: boolean
  suggested_next_step?: string | null
  link?: AlertLink
}

type OpenedTask = {
  title: string
  status: string
  deadline?: string | null
}

type OpenedRun = {
  instruction: string
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
  manage?: boolean
}

type AccountProfile = {
  id: string
  email: string
  display_name: string
  timezone?: string | null
}

type OrganizationSummary = {
  id: string
  name: string
  role: string
}

type PendingInvitation = {
  token: string
  organization_name: string
  role: string
}

type SettingsSection = "profile" | "team" | "appearance" | "security" | "timezone"

const settingsRows: { id: SettingsSection; label: string }[] = [
  { id: "profile", label: "Profile" },
  { id: "team", label: "Team" },
  { id: "appearance", label: "Appearance" },
  { id: "security", label: "Security" },
  { id: "timezone", label: "Timezone" }
]

function workspaceTitle(name: string, displayName: string) {
  if (name.trim().toLowerCase() === displayName.trim().toLowerCase()) {
    return "Personal workspace"
  }
  return name
}

const fieldClass =
  "w-full rounded-md border border-border bg-[hsl(var(--chat-canvas))] px-2.5 py-1.5 text-[13px] text-foreground outline-none focus:border-foreground"

const saveButtonClass =
  "rounded-md border border-border bg-[hsl(var(--chat-canvas))] px-2.5 py-1 text-xs font-medium text-foreground transition-colors hover:border-foreground hover:bg-foreground hover:text-background"

function timezoneChoices() {
  const supported =
    typeof Intl !== "undefined" && "supportedValuesOf" in Intl
      ? Intl.supportedValuesOf("timeZone")
      : []
  return supported.length > 0 ? supported : ["UTC"]
}

function publishDisplayName(name: string) {
  window.dispatchEvent(new CustomEvent("cognilance-profile", { detail: name }))
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
  if (status === "paused") return "Paused"
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
  const {
    setChatMessages,
    setUserInput,
    chatMessages,
    isGenerating,
    setActiveDocument,
    setDocumentPaneOpen
  } = useContext(ChatbotUIContext)
  const generatingRef = useRef(isGenerating)
  generatingRef.current = isGenerating
  const shareMessages = (
    conversationId: string,
    messages: Parameters<typeof watchSharedConversation>[1]
  ) => {
    watchSharedConversation(conversationId, messages, setChatMessages, () => generatingRef.current)
  }

  const showSavedDocument = async (
    messages: ReturnType<typeof toChatMessages>,
    documentId: string | null | undefined
  ) => {
    const document = documentId ? await fetchDocxDocument(documentId) : null
    setActiveDocument(document)
    setDocumentPaneOpen(document !== null)
    return withActiveDocument(messages, document)
  }

  useEffect(() => {
    const storedId = getConversationId()
    if (storedId && !getCognilanceSnapshot().id) {
      setCognilanceConversation(storedId)
    }
  }, [])

  useEffect(() => {
    return () => stopSharedConversation()
  }, [snapshot.id])

  useEffect(() => {
    const id = snapshot.id
    if (!id || chatMessages.length > 0) return
    let cancelled = false
    cognilanceJson(`conversations/${id}`)
      .then(async payload => {
        if (cancelled) return
        const loaded = await showSavedDocument(
          toChatMessages(payload.messages || [], id),
          payload.active_docx
        )
        if (cancelled) return
        setChatMessages(current => (current.length > 0 ? current : loaded))
        setHasEarlier((payload.messages || []).length >= MESSAGE_PAGE)
        shareMessages(id, loaded)
        if (payload.title) setCognilanceConversation(id, payload.title)
      })
      .catch(() => {})
    return () => {
      cancelled = true
    }
  }, [snapshot.id, chatMessages.length, setChatMessages])
  const [conversations, setConversations] = useState<ConversationItem[]>([])
  const [sessions, setSessions] = useState<SessionItem[]>([])
  const [alerts, setAlerts] = useState<AlertItem[]>([])
  const [openedTask, setOpenedTask] = useState<OpenedTask | null>(null)
  const [openedRun, setOpenedRun] = useState<OpenedRun | null>(null)
  const [integrations, setIntegrations] = useState<IntegrationItem[]>([])
  const { theme, setTheme } = useTheme()
  const [account, setAccount] = useState<AccountProfile | null>(null)
  const [displayName, setDisplayName] = useState("")
  const [timezone, setTimezone] = useState("")
  const [currentPassword, setCurrentPassword] = useState("")
  const [newPassword, setNewPassword] = useState("")
  const [confirmPassword, setConfirmPassword] = useState("")
  const [passwordError, setPasswordError] = useState("")
  const [passwordSaved, setPasswordSaved] = useState(false)
  const [settingsSection, setSettingsSection] = useState<SettingsSection | null>(null)
  const [error, setError] = useState("")
  const [loading, setLoading] = useState(false)
  const [organizations, setOrganizations] = useState<OrganizationSummary[]>([])
  const [invitations, setInvitations] = useState<PendingInvitation[]>([])
  const [inviteEmail, setInviteEmail] = useState("")
  const [inviteNotice, setInviteNotice] = useState("")
  const [inviteError, setInviteError] = useState("")

  useEffect(() => {
    let cancelled = false
    const load = async () => {
      setLoading(true)
      setError("")
      try {
        if (contentType === "account") {
          try {
            const payload = await cognilanceJson("auth/me")
            if (!cancelled) {
              const profile = payload as AccountProfile
              setAccount(profile)
              setDisplayName(String(profile.display_name || ""))
              setTimezone(
                profile.timezone ||
                  Intl.DateTimeFormat().resolvedOptions().timeZone ||
                  "UTC"
              )
            }
          } catch {
            if (!cancelled) {
              setAccount(null)
              setOrganizations([])
              setInvitations([])
            }
            return
          }
          try {
            const [orgPayload, invitePayload] = await Promise.all([
              cognilanceJson("organizations"),
              cognilanceJson("invitations")
            ])
            if (!cancelled) {
              const listed = orgPayload as { organizations?: OrganizationSummary[] }
              const pending = invitePayload as { invitations?: PendingInvitation[] }
              setOrganizations(listed.organizations || [])
              setInvitations(pending.invitations || [])
            }
          } catch {
            if (!cancelled) {
              setOrganizations([])
              setInvitations([])
            }
          }
          return
        }
        if (contentType === "sessions") {
          const alertPayload = await cognilanceJson("alerts")
          if (!cancelled) setAlerts(alertPayload.alerts || [])
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

  useEffect(() => {
    if (contentType !== "account") setSettingsSection(null)
  }, [contentType])

  const openConversation = async (item: ConversationItem) => {
    setCognilanceConversation(item.id, item.title)
    setUserInput("")
    try {
      const payload = await cognilanceJson(`conversations/${item.id}`)
      setChatMessages(
        await showSavedDocument(
          toChatMessages(payload.messages || [], item.id),
          payload.active_docx
        )
      )
      setHasEarlier((payload.messages || []).length >= MESSAGE_PAGE)
      shareMessages(item.id, toChatMessages(payload.messages || [], item.id))
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
      setActiveDocument(null)
      setDocumentPaneOpen(false)
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
          setActiveDocument(null)
          setDocumentPaneOpen(false)
          setUserInput("")
        }
      }
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Couldn't delete that conversation."
      )
    }
  }

  const saveProfile = async (event: FormEvent) => {
    event.preventDefault()
    setError("")
    try {
      const payload = (await cognilanceJson("auth/me", {
        method: "PATCH",
        body: JSON.stringify({ display_name: displayName })
      })) as AccountProfile
      setAccount(payload)
      publishDisplayName(payload.display_name)
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't update profile.")
    }
  }

  const saveTimezone = async (nextZone: string) => {
    setTimezone(nextZone)
    setError("")
    try {
      const payload = (await cognilanceJson("auth/me", {
        method: "PATCH",
        body: JSON.stringify({ timezone: nextZone })
      })) as AccountProfile
      setAccount(payload)
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't update timezone.")
    }
  }

  const savePassword = async (event: FormEvent) => {
    event.preventDefault()
    setPasswordError("")
    setPasswordSaved(false)
    if (newPassword.length < 8) {
      setPasswordError("Password must be at least 8 characters.")
      return
    }
    if (newPassword !== confirmPassword) {
      setPasswordError("Passwords do not match.")
      return
    }
    try {
      await cognilanceJson("auth/password", {
        method: "POST",
        body: JSON.stringify({
          current_password: currentPassword,
          new_password: newPassword
        })
      })
      setCurrentPassword("")
      setNewPassword("")
      setConfirmPassword("")
      setPasswordSaved(true)
    } catch (err) {
      setPasswordError(
        err instanceof Error ? err.message : "Couldn't update password."
      )
    }
  }

  const refreshMembership = async () => {
    const [orgPayload, invitePayload] = await Promise.all([
      cognilanceJson("organizations"),
      cognilanceJson("invitations")
    ])
    const listed = orgPayload as { organizations?: OrganizationSummary[] }
    const pending = invitePayload as { invitations?: PendingInvitation[] }
    setOrganizations(listed.organizations || [])
    setInvitations(pending.invitations || [])
  }

  const sendInvite = async (event: FormEvent) => {
    event.preventDefault()
    const organization = organizations[0]
    const email = inviteEmail.trim()
    if (!organization || !email) return
    setInviteError("")
    setInviteNotice("")
    try {
      await cognilanceJson(`organizations/${organization.id}/invitations`, {
        method: "POST",
        body: JSON.stringify({ email, role: "member" })
      })
      setInviteEmail("")
      setInviteNotice("Invitation sent.")
    } catch (err) {
      setInviteError(err instanceof Error ? err.message : "Could not send the invitation.")
    }
  }

  const acceptInvite = async (token: string) => {
    setInviteError("")
    setInviteNotice("")
    try {
      await cognilanceJson(`invitations/${token}/accept`, { method: "POST" })
      await refreshMembership()
      setInviteNotice("Invitation accepted.")
    } catch (err) {
      setInviteError(err instanceof Error ? err.message : "Could not accept the invitation.")
    }
  }

  const logout = async () => {
    setError("")
    setLoading(true)
    try {
      await cognilanceJson("auth/logout", { method: "POST" })
      setAccount(null)
      setConversations([])
      setSessions([])
      clearOrchestratorConversation()
      setChatMessages([])
      setActiveDocument(null)
      setDocumentPaneOpen(false)
      setUserInput("")
      router.replace("/login")
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't sign out.")
    } finally {
      setLoading(false)
    }
  }

  if (contentType === "account") {
    const initial = (account?.display_name || account?.email || "?").trim().charAt(0).toUpperCase()
    const zones = timezoneChoices()
    const appearance = [
      { id: "light", label: "Light" },
      { id: "dark", label: "Dark" },
      { id: "system", label: "System" }
    ]
    const organization = organizations[0]
    const canInvite =
      organization?.role === "owner" || organization?.role === "admin"
    const sectionTitle =
      settingsRows.find(row => row.id === settingsSection)?.label || "Settings"
    const rowClass =
      "flex w-full items-center justify-between gap-3 rounded-lg px-2 py-2.5 text-left text-[13.5px] text-foreground transition-colors hover:bg-accent/70"

    return (
      <Panel
        title={sectionTitle}
        loading={loading}
        error={error}
        action={
          settingsSection ? (
            <button
              type="button"
              className="text-muted-foreground flex size-7 items-center justify-center rounded-md border border-border transition-colors hover:border-foreground hover:text-foreground"
              aria-label="Back to settings"
              onClick={() => setSettingsSection(null)}
            >
              <IconChevronLeft size={16} stroke={1.75} />
            </button>
          ) : undefined
        }
      >
        {account ? (
          settingsSection === null ? (
            <div className="flex h-full min-h-0 flex-col pb-2">
              <div className="flex items-center gap-3 px-2 py-2">
                <div className="font-[family-name:var(--font-display)] flex size-9 shrink-0 items-center justify-center rounded-full bg-foreground text-sm font-semibold text-background">
                  {initial}
                </div>
                <div className="min-w-0">
                  <div className="truncate text-[13.5px] font-medium text-foreground">
                    {account.display_name}
                  </div>
                  <div className="text-muted-foreground truncate text-xs">{account.email}</div>
                </div>
              </div>
              <div className="mt-1 space-y-0.5">
                {settingsRows.map(row => (
                  <button
                    key={row.id}
                    type="button"
                    className={rowClass}
                    onClick={() => setSettingsSection(row.id)}
                  >
                    <span>{row.label}</span>
                    <IconChevronRight size={16} stroke={1.75} className="text-muted-foreground" />
                  </button>
                ))}
              </div>
              <div className="mt-auto border-t border-border/70 pt-2">
                <button
                  type="button"
                  className="flex w-full items-center gap-3 rounded-lg px-2 py-2 text-left text-[13.5px] text-foreground transition-colors hover:bg-accent/70"
                  onClick={() => void logout()}
                >
                  <IconLogout size={16} stroke={1.75} className="text-muted-foreground" />
                  Log out
                </button>
              </div>
            </div>
          ) : (
            <div className="space-y-3 px-2 pb-4">
              {settingsSection === "profile" ? (
                <form className="space-y-2" onSubmit={event => void saveProfile(event)}>
                  <label className="block space-y-1">
                    <span className="text-[11px] font-medium text-muted-foreground">
                      Display name
                    </span>
                    <input
                      className={fieldClass}
                      value={displayName}
                      onChange={event => setDisplayName(event.target.value)}
                    />
                  </label>
                  <button type="submit" className={saveButtonClass}>
                    Save
                  </button>
                </form>
              ) : null}

              {settingsSection === "team" ? (
                <div className="space-y-3">
                  {organization ? (
                    <div>
                      <div className="truncate text-[13.5px] font-medium text-foreground">
                        {workspaceTitle(organization.name, account.display_name)}
                      </div>
                      <div className="text-muted-foreground text-xs capitalize">
                        {organization.role}
                      </div>
                    </div>
                  ) : (
                    <p className="text-muted-foreground text-xs">No workspace yet.</p>
                  )}
                  {canInvite ? (
                    <form className="space-y-2" onSubmit={event => void sendInvite(event)}>
                      <label className="block space-y-1">
                        <span className="text-[11px] font-medium text-muted-foreground">
                          Invite a teammate
                        </span>
                        <input
                          type="email"
                          className={fieldClass}
                          value={inviteEmail}
                          onChange={event => setInviteEmail(event.target.value)}
                          placeholder="name@example.com"
                        />
                      </label>
                      <button type="submit" className={saveButtonClass}>
                        Invite
                      </button>
                    </form>
                  ) : null}
                  {invitations.map(invitation => (
                    <div
                      key={invitation.token}
                      className="flex items-center justify-between gap-2"
                    >
                      <div className="min-w-0">
                        <div className="truncate text-[13px] text-foreground">
                          {workspaceTitle(invitation.organization_name, account.display_name)}
                        </div>
                        <div className="text-muted-foreground text-xs capitalize">
                          {invitation.role}
                        </div>
                      </div>
                      <button
                        type="button"
                        className={saveButtonClass}
                        onClick={() => void acceptInvite(invitation.token)}
                      >
                        Accept
                      </button>
                    </div>
                  ))}
                  {inviteNotice ? (
                    <p className="text-muted-foreground text-xs">{inviteNotice}</p>
                  ) : null}
                  {inviteError ? (
                    <p className="text-xs text-red-500">{inviteError}</p>
                  ) : null}
                </div>
              ) : null}

              {settingsSection === "appearance" ? (
                <div className="grid grid-cols-3 gap-1">
                  {appearance.map(choice => {
                    const selected = theme === choice.id
                    return (
                      <button
                        key={choice.id}
                        type="button"
                        className={cn(
                          "rounded-md border px-2 py-1.5 text-xs font-medium transition-colors",
                          selected
                            ? "border-foreground bg-foreground text-background"
                            : "border-border bg-[hsl(var(--chat-canvas))] text-foreground hover:border-foreground"
                        )}
                        onClick={() => setTheme(choice.id)}
                      >
                        {choice.label}
                      </button>
                    )
                  })}
                </div>
              ) : null}

              {settingsSection === "security" ? (
                <form className="space-y-2" onSubmit={event => void savePassword(event)}>
                  <label className="block space-y-1">
                    <span className="text-[11px] font-medium text-muted-foreground">
                      Current password
                    </span>
                    <input
                      type="password"
                      autoComplete="current-password"
                      className={fieldClass}
                      value={currentPassword}
                      onChange={event => setCurrentPassword(event.target.value)}
                    />
                  </label>
                  <label className="block space-y-1">
                    <span className="text-[11px] font-medium text-muted-foreground">
                      New password
                    </span>
                    <input
                      type="password"
                      autoComplete="new-password"
                      className={fieldClass}
                      value={newPassword}
                      onChange={event => setNewPassword(event.target.value)}
                    />
                  </label>
                  <label className="block space-y-1">
                    <span className="text-[11px] font-medium text-muted-foreground">
                      Confirm new password
                    </span>
                    <input
                      type="password"
                      autoComplete="new-password"
                      className={fieldClass}
                      value={confirmPassword}
                      onChange={event => setConfirmPassword(event.target.value)}
                    />
                  </label>
                  {passwordError && (
                    <p className="text-destructive text-xs">{passwordError}</p>
                  )}
                  {passwordSaved && (
                    <p className="text-muted-foreground text-xs">Password updated.</p>
                  )}
                  <button type="submit" className={saveButtonClass}>
                    Update password
                  </button>
                </form>
              ) : null}

              {settingsSection === "timezone" ? (
                <label className="block space-y-1">
                  <span className="text-[11px] font-medium text-muted-foreground">
                    Timezone
                  </span>
                  <select
                    className={fieldClass}
                    value={zones.includes(timezone) ? timezone : zones[0]}
                    onChange={event => void saveTimezone(event.target.value)}
                  >
                    {zones.map(zone => (
                      <option key={zone} value={zone}>
                        {zone}
                      </option>
                    ))}
                  </select>
                </label>
              ) : null}
            </div>
          )
        ) : (
          <div className="space-y-3 px-2">
            <p className="text-muted-foreground text-xs leading-5">
              Sign in to keep conversations tied to your account.
            </p>
            <Link
              href="/login"
              className="inline-flex rounded-md border border-border bg-[hsl(var(--chat-canvas))] px-2.5 py-1.5 text-xs font-medium text-foreground transition-colors hover:border-foreground hover:bg-foreground hover:text-background"
            >
              Go to login
            </Link>
          </div>
        )}
      </Panel>
    )
  }

  if (contentType === "integrations") {
    return (
      <Panel title="Integrations" loading={loading} error={error}>
        <div className="space-y-0.5">
          {integrations.map((item, index) => {
            const logoKey = item.logo || item.id
            const isGithub = logoKey === "github" || item.id === "github"
            const localLogo =
              isGithub || logoKey === "x" || logoKey === "reddit" || logoKey === "linkedin"
                ? `/integrations/${isGithub ? "github" : logoKey}.svg`
                : ""
            const isMonochromeSvg = isGithub || logoKey === "x"
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
                        localLogo ||
                        `/api/cognilance/integrations/logos/${encodeURIComponent(logoKey)}`
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
                      {item.manage !== false ? (
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
                      ) : null}
                    </div>
                  ) : item.manage === false ? (
                    <span className="text-[11px] font-medium text-muted-foreground">
                      Not connected
                    </span>
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

    const pauseSession = async (session: SessionItem) => {
      try {
        await cognilanceJson(`sessions/${session.id}/pause`, { method: "POST" })
        await refreshSessions()
      } catch (err) {
        setError(err instanceof Error ? err.message : "Couldn't pause that session.")
      }
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

    const refreshAlerts = async () => {
      const payload = await cognilanceJson("alerts")
      setAlerts(payload.alerts || [])
    }

    const acknowledgeAlert = async (alert: AlertItem) => {
      try {
        await cognilanceJson(`alerts/${alert.id}/acknowledge`, { method: "POST" })
        await refreshAlerts()
      } catch (err) {
        setError(err instanceof Error ? err.message : "Couldn't acknowledge that alert.")
      }
    }

    const dismissAlert = async (alert: AlertItem) => {
      try {
        await cognilanceJson(`alerts/${alert.id}/dismiss`, { method: "POST" })
        await refreshAlerts()
      } catch (err) {
        setError(err instanceof Error ? err.message : "Couldn't dismiss that alert.")
      }
    }

    const openAlertLink = async (alert: AlertItem) => {
      const link = alert.link || {}
      try {
        if (link.type === "conversation" && link.conversation_id) {
          await openConversation({ id: link.conversation_id, title: "" })
          return
        }
        if (link.type === "task" && link.project_id && link.task_id) {
          const task = await cognilanceJson(
            `projects/${link.project_id}/tasks/${link.task_id}`
          )
          setOpenedRun(null)
          setOpenedTask({
            title: String(task.title || "Work task"),
            status: String(task.status || ""),
            deadline: task.deadline ? String(task.deadline) : null
          })
          return
        }
        if (link.type === "run" && link.run_id) {
          const payload = await cognilanceJson(`runs/${link.run_id}`)
          const run = payload.run || payload
          const conversationId = String(run.conversation_id || "")
          if (conversationId && !conversationId.startsWith("schedule:")) {
            await openConversation({ id: conversationId, title: "" })
            return
          }
          setOpenedTask(null)
          setOpenedRun({
            instruction: String(run.instruction || "Background run")
          })
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : "Couldn't open that alert.")
      }
    }

    const useSuggestedStep = (alert: AlertItem) => {
      const text = String(alert.suggested_next_step || "").trim()
      if (!text) return
      setUserInput(text)
      const link = alert.link || {}
      if (link.type === "conversation" && link.conversation_id) {
        void openConversation({ id: link.conversation_id, title: "" })
      }
    }

    return (
      <div className="flex h-full min-h-0 flex-col overflow-y-auto">
      <Panel title="Sessions" loading={loading} error={error} fill={false}>
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
                    <div className="flex shrink-0 items-center gap-2">
                      {running ? (
                        <button
                          type="button"
                          className="rounded-[6px] px-2 py-1 text-xs font-medium text-foreground underline-offset-2 hover:underline"
                          onClick={() => void pauseSession(session)}
                        >
                          Pause
                        </button>
                      ) : null}
                      <button
                        type="button"
                        className={cn(
                          "rounded-[6px] px-2 py-1 text-xs font-medium underline-offset-2 hover:underline",
                          running ? "text-destructive" : "text-foreground"
                        )}
                        onClick={() =>
                          void (running ? stopSession(session) : startSession(session))
                        }
                        disabled={!running && !session.subscription_id}
                      >
                        {running ? "Stop" : "Start"}
                      </button>
                    </div>
                  </div>
                )
              })
            )}
          </>
        )}
      </Panel>
      <Panel title="Alerts" loading={loading} error="" fill={false}>
        {alerts.length === 0 ? (
          <p className="text-muted-foreground text-sm">No open alerts.</p>
        ) : (
          alerts.map(alert => {
            const link = alert.link || {}
            const url = link.type === "url" ? String(link.url || "") : ""
            return (
              <div
                key={alert.id}
                className="chat-row mb-2 rounded-[12px] border border-border bg-[hsl(var(--chat-surface))] p-3"
              >
                <div className="text-sm">{alert.summary}</div>
                <div className="mt-1 text-xs text-muted-foreground">
                  {alert.priority || "normal"}
                  {alert.read ? " · Read" : " · Unread"}
                  {alert.assignee_account_id ? " · Assigned" : ""}
                </div>
                <div className="mt-2 flex flex-wrap items-center gap-2">
                  {url ? (
                    <a
                      className="text-xs font-medium text-foreground underline-offset-2 hover:underline"
                      href={url}
                      target="_blank"
                      rel="noreferrer"
                    >
                      Open
                    </a>
                  ) : link.type ? (
                    <button
                      type="button"
                      className="text-xs font-medium text-foreground underline-offset-2 hover:underline"
                      onClick={() => void openAlertLink(alert)}
                    >
                      Open
                    </button>
                  ) : null}
                  <button
                    type="button"
                    className="text-xs font-medium text-foreground underline-offset-2 hover:underline"
                    onClick={() => void acknowledgeAlert(alert)}
                  >
                    Acknowledge
                  </button>
                  <button
                    type="button"
                    className="text-xs font-medium text-destructive underline-offset-2 hover:underline"
                    onClick={() => void dismissAlert(alert)}
                  >
                    Dismiss
                  </button>
                </div>
                {alert.suggested_next_step ? (
                  <div className="mt-2">
                    <p className="text-xs text-muted-foreground">
                      {alert.suggested_next_step}
                    </p>
                    <button
                      type="button"
                      className="mt-1 text-xs font-medium text-foreground underline-offset-2 hover:underline"
                      onClick={() => useSuggestedStep(alert)}
                    >
                      Use in chat
                    </button>
                  </div>
                ) : null}
              </div>
            )
          })
        )}
        {openedTask ? (
          <div className="mt-2 rounded-[12px] border border-border p-3 text-sm">
            <div>{openedTask.title}</div>
            <div className="mt-1 text-xs text-muted-foreground">
              {openedTask.status}
              {openedTask.deadline ? ` · ${openedTask.deadline}` : ""}
            </div>
          </div>
        ) : null}
        {openedRun ? (
          <div className="mt-2 rounded-[12px] border border-border p-3 text-sm">
            {openedRun.instruction}
          </div>
        ) : null}
      </Panel>
      </div>
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
  fill?: boolean
  children: React.ReactNode
}> = ({ title, eyebrow, lead, loading, error, action, fill = true, children }) => (
  <div className={cn("min-h-0 flex-col px-1", fill ? "flex h-full" : "flex shrink-0")}>
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
    <div className={cn(fill && "sidebar-panel-scroll min-h-0 flex-1 overflow-y-auto")}>
      {loading ? (
        <p className="text-muted-foreground px-2 py-2 text-xs">Loading…</p>
      ) : (
        children
      )}
    </div>
  </div>
)

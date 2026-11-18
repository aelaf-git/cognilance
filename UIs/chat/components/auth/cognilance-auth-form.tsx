"use client"

import { cognilanceJson } from "@/lib/cognilance-client"
import { clearOrchestratorConversation } from "@/lib/cognilance-store"
import { cn } from "@/lib/utils"
import { useRouter } from "next/navigation"
import { FormEvent, useState } from "react"

type AuthMode = "login" | "register"

type CognilanceAuthFormProps = {
  className?: string
  initialMode?: AuthMode
  onSuccess?: () => void
}

export function CognilanceAuthForm({
  className,
  initialMode = "login",
  onSuccess
}: CognilanceAuthFormProps) {
  const router = useRouter()
  const [mode, setMode] = useState<AuthMode>(initialMode)
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [displayName, setDisplayName] = useState("")
  const [error, setError] = useState("")
  const [loading, setLoading] = useState(false)

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    setError("")
    setLoading(true)
    try {
      const path = mode === "register" ? "auth/register" : "auth/login"
      const body: Record<string, string> = { email, password }
      if (mode === "register" && displayName.trim()) {
        body.display_name = displayName.trim()
      }
      await cognilanceJson(path, {
        method: "POST",
        body: JSON.stringify(body)
      })
      clearOrchestratorConversation()
      onSuccess?.()
      router.replace("/local/chat")
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't sign in.")
    } finally {
      setLoading(false)
    }
  }

  const fieldClass =
    "w-full rounded-lg border border-border/80 bg-[hsl(var(--chat-surface))] px-3 py-2.5 text-[14px] text-foreground outline-none transition-colors placeholder:text-muted-foreground/70 focus:border-foreground"

  return (
    <form className={cn("space-y-4", className)} onSubmit={event => void submit(event)}>
      <div className="flex gap-1 rounded-lg border border-border/70 bg-[hsl(var(--chat-surface))] p-1">
        <button
          type="button"
          className={cn(
            "font-[family-name:var(--font-display)] flex-1 rounded-md px-3 py-2 text-sm font-medium transition-colors",
            mode === "login"
              ? "bg-foreground text-background"
              : "text-muted-foreground hover:text-foreground"
          )}
          onClick={() => setMode("login")}
        >
          Log in
        </button>
        <button
          type="button"
          className={cn(
            "font-[family-name:var(--font-display)] flex-1 rounded-md px-3 py-2 text-sm font-medium transition-colors",
            mode === "register"
              ? "bg-foreground text-background"
              : "text-muted-foreground hover:text-foreground"
          )}
          onClick={() => setMode("register")}
        >
          Register
        </button>
      </div>

      {mode === "register" && (
        <label className="block space-y-1.5">
          <span className="font-[family-name:var(--font-display)] text-[11px] font-semibold uppercase tracking-[0.12em] text-muted-foreground">
            Display name
          </span>
          <input
            className={fieldClass}
            value={displayName}
            onChange={event => setDisplayName(event.target.value)}
            autoComplete="nickname"
            placeholder="How should we address you?"
          />
        </label>
      )}

      <label className="block space-y-1.5">
        <span className="font-[family-name:var(--font-display)] text-[11px] font-semibold uppercase tracking-[0.12em] text-muted-foreground">
          Email
        </span>
        <input
          type="email"
          required
          className={fieldClass}
          value={email}
          onChange={event => setEmail(event.target.value)}
          autoComplete="email"
          placeholder="you@company.com"
        />
      </label>

      <label className="block space-y-1.5">
        <span className="font-[family-name:var(--font-display)] text-[11px] font-semibold uppercase tracking-[0.12em] text-muted-foreground">
          Password
        </span>
        <input
          type="password"
          required
          minLength={8}
          className={fieldClass}
          value={password}
          onChange={event => setPassword(event.target.value)}
          autoComplete={mode === "register" ? "new-password" : "current-password"}
          placeholder="At least 8 characters"
        />
      </label>

      {error && <p className="text-destructive text-sm">{error}</p>}

      <button
        type="submit"
        disabled={loading}
        className="font-[family-name:var(--font-display)] w-full rounded-lg bg-foreground px-4 py-2.5 text-sm font-semibold text-background transition-opacity hover:opacity-90 disabled:opacity-60"
      >
        {loading
          ? "Working…"
          : mode === "register"
            ? "Create account"
            : "Log in"}
      </button>
    </form>
  )
}

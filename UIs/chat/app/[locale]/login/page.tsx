"use client"

import { CognilanceAuthForm } from "@/components/auth/cognilance-auth-form"
import { cognilanceJson } from "@/lib/cognilance-client"
import { useRouter } from "next/navigation"
import { useEffect, useState } from "react"

export default function LoginPage() {
  const router = useRouter()
  const [checking, setChecking] = useState(true)

  useEffect(() => {
    let cancelled = false
    cognilanceJson("auth/me")
      .then(() => {
        if (!cancelled) router.replace("/local/chat")
      })
      .catch(() => {
        if (!cancelled) setChecking(false)
      })
    return () => {
      cancelled = true
    }
  }, [router])

  if (checking) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-[hsl(var(--chat-canvas))] text-muted-foreground">
        <p className="font-[family-name:var(--font-display)] text-sm">Loading…</p>
      </div>
    )
  }

  return (
    <div className="relative min-h-screen overflow-hidden bg-[hsl(var(--chat-canvas))] text-foreground">
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0"
        style={{
          backgroundImage:
            "radial-gradient(ellipse 80% 55% at 12% 18%, hsl(0 0% 0% / 0.05), transparent 55%), radial-gradient(ellipse 70% 50% at 88% 78%, hsl(0 0% 0% / 0.04), transparent 50%), linear-gradient(165deg, hsl(var(--chat-canvas)) 0%, hsl(var(--chat-surface)) 48%, hsl(var(--chat-canvas)) 100%)"
        }}
      />
      <main className="relative z-10 mx-auto flex min-h-screen w-full max-w-md flex-col justify-center px-6 py-12">
        <div className="mb-10 flex flex-col items-start gap-4">
          <img
            src="/brand/Cognilance-Logo.png"
            alt=""
            className="size-11 object-contain"
          />
          <div>
            <h1 className="font-[family-name:var(--font-display)] text-4xl font-semibold tracking-tight text-foreground sm:text-5xl">
              Cognilance
            </h1>
            <p className="text-muted-foreground mt-3 max-w-sm text-[15px] leading-6">
              Sign in to continue your conversations with the coordinator.
            </p>
          </div>
        </div>

        <CognilanceAuthForm />
      </main>
    </div>
  )
}

"use client"

import { ChatbotUIContext } from "@/context/context"
import { useContext } from "react"

export default function WorkspacePage() {
  const { selectedWorkspace } = useContext(ChatbotUIContext)

  return (
    <div className="chat-canvas flex h-screen w-full flex-col items-center justify-center gap-3 px-6 text-center">
      <p className="font-[family-name:var(--font-display)] text-[0.75rem] font-semibold uppercase tracking-[0.12em] text-muted-foreground">
        Workspace
      </p>
      <h1 className="font-[family-name:var(--font-display)] text-3xl font-semibold tracking-tight text-foreground">
        {selectedWorkspace?.name || "Cognilance"}
      </h1>
      <p className="max-w-sm text-sm text-muted-foreground">
        Open Conversations from the sidebar to continue.
      </p>
    </div>
  )
}

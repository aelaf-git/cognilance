"use client"

import { cognilanceJson } from "@/lib/cognilance-client"
import { cn } from "@/lib/utils"
import { IconMessage, IconPlayerPlay, IconPlugConnected, IconUser } from "@tabler/icons-react"
import { FC, useEffect, useState } from "react"
import { TabsList } from "../ui/tabs"
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "../ui/tooltip"
import { SidebarSwitchItem } from "./sidebar-switch-item"

export const SIDEBAR_ICON_SIZE = 20

interface SidebarSwitcherProps {
  contentType: string
  onContentTypeChange: (contentType: string) => void
}

export const SidebarSwitcher: FC<SidebarSwitcherProps> = ({
  contentType,
  onContentTypeChange
}) => {
  const [name, setName] = useState("")

  useEffect(() => {
    let cancelled = false
    cognilanceJson("auth/me")
      .then(payload => {
        if (!cancelled) setName(String(payload.display_name || payload.email || ""))
      })
      .catch(() => {
        if (!cancelled) setName("")
      })
    const onProfile = (event: Event) => {
      const next = (event as CustomEvent<string>).detail
      if (next) setName(next)
    }
    window.addEventListener("cognilance-profile", onProfile)
    return () => {
      cancelled = true
      window.removeEventListener("cognilance-profile", onProfile)
    }
  }, [contentType])

  const initial = name.trim().charAt(0).toUpperCase()
  const accountOpen = contentType === "account"

  return (
    <div className="flex h-full flex-col justify-between bg-transparent">
      <TabsList className="flex h-auto w-full flex-col items-center gap-1.5 bg-transparent py-2.5">
        <SidebarSwitchItem
          icon={<IconMessage size={SIDEBAR_ICON_SIZE} stroke={1.75} />}
          contentType="chats"
          label="Conversations"
          onContentTypeChange={onContentTypeChange}
        />

        <SidebarSwitchItem
          icon={<IconPlayerPlay size={SIDEBAR_ICON_SIZE} stroke={1.75} />}
          contentType="sessions"
          label="Sessions"
          onContentTypeChange={onContentTypeChange}
        />

        <SidebarSwitchItem
          icon={<IconPlugConnected size={SIDEBAR_ICON_SIZE} stroke={1.75} />}
          contentType="integrations"
          label="Integrations"
          onContentTypeChange={onContentTypeChange}
        />
      </TabsList>

      <div className="flex w-full justify-center pb-3">
        <TooltipProvider delayDuration={500}>
          <Tooltip>
            <TooltipTrigger asChild>
              <button
                type="button"
                aria-label={name || "Account"}
                onClick={() => onContentTypeChange("account")}
                className={cn(
                  "chat-press font-[family-name:var(--font-display)] flex size-9 items-center justify-center rounded-full text-[13px] font-semibold",
                  accountOpen
                    ? "bg-foreground text-background"
                    : "border border-border bg-transparent text-foreground hover:bg-accent"
                )}
              >
                {initial || <IconUser size={SIDEBAR_ICON_SIZE} stroke={1.75} />}
              </button>
            </TooltipTrigger>
            <TooltipContent side="right">{name || "Account"}</TooltipContent>
          </Tooltip>
        </TooltipProvider>
      </div>
    </div>
  )
}

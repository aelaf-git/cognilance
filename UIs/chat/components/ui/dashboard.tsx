"use client"

import { Sidebar } from "@/components/sidebar/sidebar"
import { SidebarSwitcher } from "@/components/sidebar/sidebar-switcher"
import { Tabs } from "@/components/ui/tabs"
import { cn } from "@/lib/utils"
import { usePathname, useRouter, useSearchParams } from "next/navigation"
import { FC, useState } from "react"
import { CommandK } from "../utility/command-k"

export const SIDEBAR_WIDTH = 350
export const ICON_RAIL_WIDTH = 60
export const SIDEBAR_PANEL_WIDTH = SIDEBAR_WIDTH - ICON_RAIL_WIDTH

interface DashboardProps {
  children: React.ReactNode
}

export const Dashboard: FC<DashboardProps> = ({ children }) => {
  const pathname = usePathname()
  const router = useRouter()
  const searchParams = useSearchParams()
  const requestedTab = searchParams.get("tab") || "chats"
  const tabValue =
    requestedTab === "sessions" || requestedTab === "integrations"
      ? requestedTab
      : "chats"

  const [contentType, setContentType] = useState(tabValue)
  const [showSidebar, setShowSidebar] = useState(
    localStorage.getItem("showSidebar") !== "false"
  )

  const leftWidth = ICON_RAIL_WIDTH + (showSidebar ? SIDEBAR_PANEL_WIDTH : 0)

  const setSidebarOpen = (open: boolean) => {
    setShowSidebar(open)
    localStorage.setItem("showSidebar", String(open))
  }

  const handleRailSelect = (nextType: string) => {
    if (showSidebar && nextType === contentType) {
      setSidebarOpen(false)
      return
    }

    setContentType(nextType)
    setSidebarOpen(true)
    router.replace(`${pathname}?tab=${nextType}`)
  }

  const handleBrandClick = () => {
    setSidebarOpen(!showSidebar)
  }

  return (
    <div className="flex size-full">
      <CommandK />

      <Tabs
        className="sidebar-shell relative flex h-full shrink-0 flex-col"
        value={contentType}
        onValueChange={() => {
          // Selection is handled in SidebarSwitchItem so re-clicks can collapse.
        }}
        style={{
          "--sidebar-left-width": `${leftWidth}px`,
          "--sidebar-panel-width": `${SIDEBAR_PANEL_WIDTH}px`
        } as React.CSSProperties}
      >
        <div
          className="sidebar-brand-bar sticky top-0 z-30 flex h-14 shrink-0 items-center"
        >
          {/* Logo stays pinned in the rail column so it never shifts on expand/collapse */}
          <button
            type="button"
            onClick={handleBrandClick}
            aria-label={
              showSidebar ? "Collapse Cognilance sidebar" : "Expand Cognilance sidebar"
            }
            className="flex h-full shrink-0 items-center justify-center outline-none focus-visible:outline-none"
            style={{ width: `${ICON_RAIL_WIDTH}px` }}
          >
            <img
              src="/brand/Cognilance-Logo.png"
              alt=""
              className="size-8 object-contain"
            />
          </button>

          {showSidebar && (
            <span className="sidebar-brand-wordmark brand-wordmark min-w-0 truncate pr-3 text-base text-foreground">
              Cognilance
            </span>
          )}
        </div>

        <div className="flex min-h-0 flex-1">
          <div
            className="sidebar-icon-rail sticky top-14 z-20 shrink-0 self-stretch"
            style={{
              minWidth: `${ICON_RAIL_WIDTH}px`,
              maxWidth: `${ICON_RAIL_WIDTH}px`,
              width: `${ICON_RAIL_WIDTH}px`
            }}
          >
            <SidebarSwitcher onContentTypeChange={handleRailSelect} />
          </div>

          <div
            className={cn(
              "sidebar-panel h-full overflow-hidden duration-200",
              showSidebar
                ? "sidebar-panel-open"
                : "sidebar-panel-closed"
            )}
          >
            {showSidebar && (
              <Sidebar contentType={contentType} showSidebar={showSidebar} />
            )}
          </div>
        </div>
      </Tabs>

      <div className="relative flex min-w-0 grow flex-col">
        {children}
      </div>
    </div>
  )
}

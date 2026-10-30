"use client"

import { Sidebar } from "@/components/sidebar/sidebar"
import { SidebarSwitcher } from "@/components/sidebar/sidebar-switcher"
import { Tabs } from "@/components/ui/tabs"
import { cn } from "@/lib/utils"
import { usePathname, useRouter, useSearchParams } from "next/navigation"
import { FC, useCallback, useEffect, useState } from "react"
import { CommandK } from "../utility/command-k"

export const ICON_RAIL_WIDTH = 52
export const SIDEBAR_PANEL_WIDTH = 320
export const MIN_PANEL_WIDTH = 240
export const MAX_PANEL_WIDTH = 520
export const SIDEBAR_WIDTH = ICON_RAIL_WIDTH + SIDEBAR_PANEL_WIDTH

const clampPanelWidth = (value: number) =>
  Math.min(MAX_PANEL_WIDTH, Math.max(MIN_PANEL_WIDTH, Math.round(value)))

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
  const [panelWidth, setPanelWidth] = useState<number>(() => {
    const saved = Number(localStorage.getItem("sidebarPanelWidth"))
    return Number.isFinite(saved) && saved > 0
      ? clampPanelWidth(saved)
      : SIDEBAR_PANEL_WIDTH
  })
  const [isResizing, setIsResizing] = useState(false)

  const leftWidth = ICON_RAIL_WIDTH + (showSidebar ? panelWidth : 0)

  const setSidebarOpen = (open: boolean) => {
    setShowSidebar(open)
    localStorage.setItem("showSidebar", String(open))
  }

  const updatePanelWidth = useCallback((nextWidth: number) => {
    const clamped = clampPanelWidth(nextWidth)
    setPanelWidth(clamped)
    localStorage.setItem("sidebarPanelWidth", String(clamped))
  }, [])

  useEffect(() => {
    if (!isResizing) return

    const handlePointerMove = (event: PointerEvent) => {
      updatePanelWidth(event.clientX - ICON_RAIL_WIDTH)
    }

    const stopResizing = () => {
      setIsResizing(false)
      document.body.style.cursor = ""
      document.body.style.userSelect = ""
    }

    document.body.style.cursor = "col-resize"
    document.body.style.userSelect = "none"
    window.addEventListener("pointermove", handlePointerMove)
    window.addEventListener("pointerup", stopResizing)
    window.addEventListener("pointercancel", stopResizing)

    return () => {
      window.removeEventListener("pointermove", handlePointerMove)
      window.removeEventListener("pointerup", stopResizing)
      window.removeEventListener("pointercancel", stopResizing)
      document.body.style.cursor = ""
      document.body.style.userSelect = ""
    }
  }, [isResizing, updatePanelWidth])

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
        className={cn(
          "sidebar-shell relative flex h-full shrink-0 flex-col",
          isResizing && "sidebar-resizing"
        )}
        value={contentType}
        onValueChange={() => {
          // Selection is handled in SidebarSwitchItem so re-clicks can collapse.
        }}
        style={{
          "--sidebar-left-width": `${leftWidth}px`,
          "--sidebar-panel-width": `${panelWidth}px`
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
              className="size-7 object-contain"
            />
          </button>

          {showSidebar && (
            <span className="sidebar-brand-wordmark brand-wordmark min-w-0 truncate pl-1 pr-3 text-[15px] font-semibold tracking-tight text-foreground">
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
              "sidebar-panel h-full overflow-hidden",
              showSidebar ? "sidebar-panel-open" : "sidebar-panel-closed"
            )}
          >
            {showSidebar && (
              <Sidebar contentType={contentType} showSidebar={showSidebar} />
            )}
          </div>
        </div>

        {showSidebar && (
          <div
            role="separator"
            aria-orientation="vertical"
            aria-label="Resize sidebar"
            title="Drag to resize · Double-click to reset"
            onPointerDown={event => {
              event.preventDefault()
              setIsResizing(true)
            }}
            onDoubleClick={() => updatePanelWidth(SIDEBAR_PANEL_WIDTH)}
            className={cn(
              "group absolute inset-y-0 -right-1 z-40 hidden w-2 cursor-col-resize items-stretch justify-center sm:flex"
            )}
          >
            <div
              className={cn(
                "h-full w-[2px] transition-colors",
                isResizing
                  ? "bg-foreground/50"
                  : "bg-transparent group-hover:bg-foreground/30"
              )}
            />
          </div>
        )}
      </Tabs>

      <div className="relative flex min-w-0 grow flex-col">
        {children}
      </div>
    </div>
  )
}

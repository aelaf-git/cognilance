"use client"

import { FC } from "react"
import { SIDEBAR_PANEL_WIDTH } from "../ui/dashboard"
import { TabsContent } from "../ui/tabs"
import { CognilanceSidebar } from "./cognilance-sidebar"

interface SidebarProps {
  contentType: string
  showSidebar: boolean
}

export const Sidebar: FC<SidebarProps> = ({ contentType, showSidebar }) => {
  const panel =
    contentType === "sessions" || contentType === "integrations"
      ? contentType
      : "chats"

  return (
    <TabsContent
      className="m-0 h-full w-full"
      style={{
        minWidth: showSidebar ? `${SIDEBAR_PANEL_WIDTH}px` : "0px",
        maxWidth: showSidebar ? `${SIDEBAR_PANEL_WIDTH}px` : "0px",
        width: showSidebar ? `${SIDEBAR_PANEL_WIDTH}px` : "0px"
      }}
      value={contentType}
    >
      <div className="flex h-full flex-col px-3 pb-3 pt-2">
        <CognilanceSidebar contentType={panel} />
      </div>
    </TabsContent>
  )
}

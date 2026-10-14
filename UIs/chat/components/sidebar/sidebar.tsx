"use client"

import { FC } from "react"
import { SIDEBAR_WIDTH } from "../ui/dashboard"
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
      className="m-0 w-full"
      style={{
        minWidth: showSidebar ? `calc(${SIDEBAR_WIDTH}px - 60px)` : "0px",
        maxWidth: showSidebar ? `calc(${SIDEBAR_WIDTH}px - 60px)` : "0px",
        width: showSidebar ? `calc(${SIDEBAR_WIDTH}px - 60px)` : "0px"
      }}
      value={contentType}
    >
      <div className="flex h-full flex-col p-3">
        <CognilanceSidebar contentType={panel} />
      </div>
    </TabsContent>
  )
}

"use client"

import { FC } from "react"
import { TabsContent } from "../ui/tabs"
import { CognilanceSidebar } from "./cognilance-sidebar"

interface SidebarProps {
  contentType: string
  showSidebar: boolean
}

export const Sidebar: FC<SidebarProps> = ({ contentType }) => {
  const panel =
    contentType === "sessions" || contentType === "integrations"
      ? contentType
      : "chats"

  return (
    <TabsContent
      className="m-0 h-full w-full"
      value={contentType}
    >
      <div
        key={contentType}
        className="chat-panel-in flex h-full flex-col px-3 pb-3 pt-3"
      >
        <CognilanceSidebar contentType={panel} />
      </div>
    </TabsContent>
  )
}

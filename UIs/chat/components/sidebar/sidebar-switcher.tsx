import {
  IconMessage,
  IconPlayerPlay,
  IconPlugConnected
} from "@tabler/icons-react"
import { FC } from "react"
import { ThemeSwitcher } from "../utility/theme-switcher"
import { TabsList } from "../ui/tabs"
import { SidebarSwitchItem } from "./sidebar-switch-item"

export const SIDEBAR_ICON_SIZE = 20

interface SidebarSwitcherProps {
  onContentTypeChange: (contentType: string) => void
}

export const SidebarSwitcher: FC<SidebarSwitcherProps> = ({
  onContentTypeChange
}) => {
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
        <ThemeSwitcher />
      </div>
    </div>
  )
}

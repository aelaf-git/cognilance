import { cn } from "@/lib/utils"
import { FC } from "react"
import { TabsTrigger } from "../ui/tabs"
import { WithTooltip } from "../ui/with-tooltip"

interface SidebarSwitchItemProps {
  contentType: string
  label?: string
  icon: React.ReactNode
  onContentTypeChange: (contentType: string) => void
}

export const SidebarSwitchItem: FC<SidebarSwitchItemProps> = ({
  contentType,
  label,
  icon,
  onContentTypeChange
}) => {
  return (
    <WithTooltip
      display={
        <div>
          {label || contentType[0].toUpperCase() + contentType.substring(1)}
        </div>
      }
      trigger={
        <TabsTrigger
          className={cn(
            "chat-press flex size-9 items-center justify-center rounded-lg p-0 text-muted-foreground hover:bg-accent hover:text-foreground hover:opacity-100",
            "data-[state=active]:bg-foreground data-[state=active]:text-background data-[state=active]:shadow-none"
          )}
          value={contentType}
          onClick={() => {
            // Re-clicking the active tab must still run our toggle handler.
            onContentTypeChange(contentType)
          }}
        >
          {icon}
        </TabsTrigger>
      }
    />
  )
}

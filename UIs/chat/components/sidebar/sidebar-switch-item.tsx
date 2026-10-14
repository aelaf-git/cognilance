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
          className="hover:opacity-50"
          value={contentType}
          onClick={() => onContentTypeChange(contentType)}
        >
          {icon}
        </TabsTrigger>
      }
    />
  )
}

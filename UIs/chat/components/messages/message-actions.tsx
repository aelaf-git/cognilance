import { ChatbotUIContext } from "@/context/context"
import { IconCheck, IconCopy, IconEdit, IconRepeat } from "@tabler/icons-react"
import { FC, useContext, useEffect, useState } from "react"
import { WithTooltip } from "../ui/with-tooltip"

export const MESSAGE_ICON_SIZE = 28

interface MessageActionsProps {
  isAssistant: boolean
  isLast: boolean
  isEditing: boolean
  onCopy: () => void
  onEdit: () => void
  onRegenerate: () => void
}

export const MessageActions: FC<MessageActionsProps> = ({
  isAssistant,
  isLast,
  isEditing,
  onCopy,
  onEdit,
  onRegenerate
}) => {
  const { isGenerating } = useContext(ChatbotUIContext)

  const [showCheckmark, setShowCheckmark] = useState(false)

  const handleCopy = () => {
    onCopy()
    setShowCheckmark(true)
  }

  useEffect(() => {
    if (showCheckmark) {
      const timer = setTimeout(() => {
        setShowCheckmark(false)
      }, 2000)

      return () => clearTimeout(timer)
    }
  }, [showCheckmark])

  const actionClass =
    "chat-motion flex size-7 items-center justify-center rounded-md transition-colors hover:bg-primary/10 hover:text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/40"

  return isEditing ? null : (
    <div className="flex items-center gap-0.5 text-muted-foreground">
      {!isAssistant && (
        <WithTooltip
          delayDuration={1000}
          side="bottom"
          display={<div>Edit</div>}
          trigger={
            <button
              type="button"
              aria-label="Edit message"
              className={actionClass}
              onClick={onEdit}
            >
              <IconEdit size={16} />
            </button>
          }
        />
      )}

      <WithTooltip
        delayDuration={1000}
        side="bottom"
        display={<div>Copy</div>}
        trigger={
          <button
            type="button"
            aria-label={showCheckmark ? "Copied" : "Copy message"}
            className={actionClass}
            onClick={handleCopy}
          >
            {showCheckmark ? <IconCheck size={16} /> : <IconCopy size={16} />}
          </button>
        }
      />

      {isAssistant && isLast && !isGenerating && (
        <WithTooltip
          delayDuration={1000}
          side="bottom"
          display={<div>Regenerate</div>}
          trigger={
            <button
              type="button"
              aria-label="Regenerate response"
              className={actionClass}
              onClick={onRegenerate}
            >
              <IconRepeat size={16} />
            </button>
          }
        />
      )}
    </div>
  )
}

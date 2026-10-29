import { ChatbotUIContext } from "@/context/context"
import useHotkey from "@/lib/hooks/use-hotkey"
import { cn } from "@/lib/utils"
import { IconArrowUp, IconPlayerStopFilled } from "@tabler/icons-react"
import { FC, useContext, useEffect, useState } from "react"
import { TextareaAutosize } from "../ui/textarea-autosize"
import { useChatHandler } from "./chat-hooks/use-chat-handler"
import { useChatHistoryHandler } from "./chat-hooks/use-chat-history"
import { usePromptAndCommand } from "./chat-hooks/use-prompt-and-command"

interface ChatInputProps {}

export const ChatInput: FC<ChatInputProps> = ({}) => {
  useHotkey("l", () => {
    handleFocusChatInput()
  })

  const [isTyping, setIsTyping] = useState<boolean>(false)

  const {
    isAssistantPickerOpen,
    focusAssistant,
    setFocusAssistant,
    userInput,
    chatMessages,
    isGenerating,
    selectedPreset,
    selectedAssistant,
    focusPrompt,
    setFocusPrompt,
    focusFile,
    focusTool,
    setFocusTool,
    isToolPickerOpen,
    isPromptPickerOpen,
    setIsPromptPickerOpen,
    isFilePickerOpen,
    setFocusFile
  } = useContext(ChatbotUIContext)

  const {
    chatInputRef,
    handleSendMessage,
    handleStopMessage,
    handleFocusChatInput
  } = useChatHandler()

  const { handleInputChange } = usePromptAndCommand()

  const {
    setNewMessageContentToNextUserMessage,
    setNewMessageContentToPreviousUserMessage
  } = useChatHistoryHandler()

  useEffect(() => {
    setTimeout(() => {
      handleFocusChatInput()
    }, 200) // FIX: hacky
  }, [selectedPreset, selectedAssistant])

  const handleKeyDown = (event: React.KeyboardEvent) => {
    if (!isTyping && event.key === "Enter" && !event.shiftKey) {
      event.preventDefault()
      setIsPromptPickerOpen(false)
      handleSendMessage(userInput, chatMessages, false)
    }

    // Consolidate conditions to avoid TypeScript error
    if (
      isPromptPickerOpen ||
      isFilePickerOpen ||
      isToolPickerOpen ||
      isAssistantPickerOpen
    ) {
      if (
        event.key === "Tab" ||
        event.key === "ArrowUp" ||
        event.key === "ArrowDown"
      ) {
        event.preventDefault()
        // Toggle focus based on picker type
        if (isPromptPickerOpen) setFocusPrompt(!focusPrompt)
        if (isFilePickerOpen) setFocusFile(!focusFile)
        if (isToolPickerOpen) setFocusTool(!focusTool)
        if (isAssistantPickerOpen) setFocusAssistant(!focusAssistant)
      }
    }

    if (event.key === "ArrowUp" && event.shiftKey && event.ctrlKey) {
      event.preventDefault()
      setNewMessageContentToPreviousUserMessage()
    }

    if (event.key === "ArrowDown" && event.shiftKey && event.ctrlKey) {
      event.preventDefault()
      setNewMessageContentToNextUserMessage()
    }

    //use shift+ctrl+up and shift+ctrl+down to navigate through chat history
    if (event.key === "ArrowUp" && event.shiftKey && event.ctrlKey) {
      event.preventDefault()
      setNewMessageContentToPreviousUserMessage()
    }

    if (event.key === "ArrowDown" && event.shiftKey && event.ctrlKey) {
      event.preventDefault()
      setNewMessageContentToNextUserMessage()
    }

    if (
      isAssistantPickerOpen &&
      (event.key === "Tab" ||
        event.key === "ArrowUp" ||
        event.key === "ArrowDown")
    ) {
      event.preventDefault()
      setFocusAssistant(!focusAssistant)
    }
  }

  const canSend = Boolean(userInput.trim())

  return (
    <div className="flex w-full flex-col gap-2">
      <div className="chat-motion flex min-h-[64px] w-full items-end gap-2 rounded-[12px] border border-[hsl(var(--chat-border))] bg-[hsl(var(--chat-surface))] px-2 py-2 pl-1 shadow-none transition-[border-color] focus-within:border-foreground/40">
        <TextareaAutosize
          textareaRef={chatInputRef}
          className="placeholder:text-muted-foreground/70 flex w-full resize-none border-none bg-transparent px-3 py-2.5 text-[15px] leading-6 focus-visible:outline-none disabled:cursor-not-allowed disabled:opacity-50"
          placeholder="Message Cognilance"
          onValueChange={handleInputChange}
          value={userInput}
          minRows={1}
          maxRows={18}
          onKeyDown={handleKeyDown}
          onCompositionStart={() => setIsTyping(true)}
          onCompositionEnd={() => setIsTyping(false)}
        />

        <div className="mb-0.5 flex shrink-0 items-center pr-0.5">
          {isGenerating ? (
            <button
              type="button"
              aria-label="Stop generating"
              className="chat-press flex size-9 items-center justify-center rounded-full border border-border bg-accent text-foreground hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              onClick={handleStopMessage}
            >
              <IconPlayerStopFilled className="animate-pulse" size={16} />
            </button>
          ) : (
            <button
              type="button"
              aria-label="Send message"
              className={cn(
                "chat-press flex size-9 items-center justify-center rounded-full focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2",
                canSend
                  ? "bg-foreground text-background hover:opacity-90"
                  : "cursor-not-allowed border border-border bg-transparent text-muted-foreground"
              )}
              onClick={() => {
                if (!canSend) return

                handleSendMessage(userInput, chatMessages, false)
              }}
              disabled={!canSend}
            >
              <IconArrowUp size={18} stroke={2} />
            </button>
          )}
        </div>
      </div>

      <p className="text-center text-[11px] leading-4 text-muted-foreground/80">
        Cognilance is an AI and can make mistakes.
      </p>
    </div>
  )
}

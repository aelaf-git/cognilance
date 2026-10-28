import { ChatbotUIContext } from "@/context/context"
import useHotkey from "@/lib/hooks/use-hotkey"
import { cn } from "@/lib/utils"
import { IconPlayerStopFilled, IconSend } from "@tabler/icons-react"
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

  return (
    <div className="chat-composer-shadow chat-motion relative flex min-h-[64px] w-full items-end rounded-[12px] border border-[hsl(var(--chat-border))] bg-[hsl(var(--chat-surface))] p-2 transition-[border-color,box-shadow] focus-within:border-foreground/40 focus-within:ring-4 focus-within:ring-foreground/5">
        <TextareaAutosize
          textareaRef={chatInputRef}
          className="placeholder:text-muted-foreground/70 flex w-full resize-none border-none bg-transparent px-3 py-2.5 pr-14 text-[15px] leading-6 focus-visible:outline-none disabled:cursor-not-allowed disabled:opacity-50"
          placeholder="Message Cognilance"
          onValueChange={handleInputChange}
          value={userInput}
          minRows={1}
          maxRows={18}
          onKeyDown={handleKeyDown}
          onCompositionStart={() => setIsTyping(true)}
          onCompositionEnd={() => setIsTyping(false)}
        />

        <div className="absolute bottom-2.5 right-2.5 flex items-center">
          {isGenerating ? (
            <button
              type="button"
              aria-label="Stop generating"
              className="flex size-9 items-center justify-center rounded-[6px] border border-border bg-accent text-foreground transition-colors hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              onClick={handleStopMessage}
            >
              <IconPlayerStopFilled className="animate-pulse" size={17} />
            </button>
          ) : (
            <button
              type="button"
              aria-label="Send message"
              className={cn(
                "flex size-9 items-center justify-center rounded-[6px] bg-primary text-primary-foreground transition-colors hover:opacity-90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2",
                !userInput.trim() &&
                  "cursor-not-allowed opacity-40 hover:opacity-40"
              )}
              onClick={() => {
                if (!userInput.trim()) return

                handleSendMessage(userInput, chatMessages, false)
              }}
              disabled={!userInput.trim()}
            >
              <IconSend size={17} />
            </button>
          )}
        </div>

        <div className="pointer-events-none absolute -bottom-5 right-1 hidden text-[10px] text-muted-foreground/60 sm:block">
          Enter to send. Shift + Enter for a new line.
        </div>
    </div>
  )
}

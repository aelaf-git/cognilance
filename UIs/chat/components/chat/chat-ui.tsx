import Loading from "@/app/[locale]/loading"
import { useChatHandler } from "@/components/chat/chat-hooks/use-chat-handler"
import { ChatbotUIContext } from "@/context/context"
import { getAssistantToolsByAssistantId } from "@/db/assistant-tools"
import { getChatFilesByChatId } from "@/db/chat-files"
import { getChatById } from "@/db/chats"
import { getMessageFileItemsByMessageId } from "@/db/message-file-items"
import { getMessagesByChatId } from "@/db/messages"
import { getMessageImageFromStorage } from "@/db/storage/message-images"
import { convertBlobToBase64 } from "@/lib/blob-to-b64"
import useHotkey from "@/lib/hooks/use-hotkey"
import { LLMID, MessageImage } from "@/types"
import { useParams } from "next/navigation"
import { FC, useContext, useEffect, useRef, useState } from "react"
import { useScroll } from "./chat-hooks/use-scroll"
import { ChatInput } from "./chat-input"
import { ChatMessages } from "./chat-messages"
import { ChatSecondaryButtons } from "./chat-secondary-buttons"
import { DocumentPane } from "./document-pane"

interface ChatUIProps {}

export const ChatUI: FC<ChatUIProps> = ({}) => {
  useHotkey("o", () => handleNewChat())

  const params = useParams()

  const {
    setChatMessages,
    setSelectedChat,
    setChatSettings,
    setChatImages,
    assistants,
    setSelectedAssistant,
    setChatFileItems,
    setChatFiles,
    setShowFilesDisplay,
    setUseRetrieval,
    setSelectedTools,
    activeDocument,
    documentPaneOpen,
    setDocumentPaneOpen
  } = useContext(ChatbotUIContext)

  const { handleNewChat, handleFocusChatInput } = useChatHandler()

  const {
    messagesStartRef,
    messagesEndRef,
    handleScroll,
    scrollToBottom,
    setIsAtBottom
  } = useScroll()

  const [loading, setLoading] = useState(true)
  const [wide, setWide] = useState(false)
  const [layoutReady, setLayoutReady] = useState(false)
  const [chatWidth, setChatWidth] = useState(460)
  const [resizing, setResizing] = useState(false)
  const splitRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const query = window.matchMedia("(min-width: 1024px)")
    const apply = () => setWide(query.matches)
    apply()
    setLayoutReady(true)
    query.addEventListener("change", apply)
    return () => query.removeEventListener("change", apply)
  }, [])

  useEffect(() => {
    if (!resizing) return

    const move = (event: PointerEvent) => {
      const bounds = splitRef.current?.getBoundingClientRect()
      if (!bounds) return
      const next = event.clientX - bounds.left
      const max = Math.max(360, bounds.width - 420)
      setChatWidth(Math.min(max, Math.max(320, next)))
    }
    const stop = () => {
      setResizing(false)
      document.body.style.cursor = ""
      document.body.style.userSelect = ""
    }

    document.body.style.cursor = "col-resize"
    document.body.style.userSelect = "none"
    window.addEventListener("pointermove", move)
    window.addEventListener("pointerup", stop)
    window.addEventListener("pointercancel", stop)
    return () => {
      window.removeEventListener("pointermove", move)
      window.removeEventListener("pointerup", stop)
      window.removeEventListener("pointercancel", stop)
      document.body.style.cursor = ""
      document.body.style.userSelect = ""
    }
  }, [resizing])

  useEffect(() => {
    const fetchData = async () => {
      await fetchMessages()
      await fetchChat()

      scrollToBottom()
      setIsAtBottom(true)
    }

    if (params.chatid) {
      fetchData().then(() => {
        handleFocusChatInput()
        setLoading(false)
      })
    } else {
      setLoading(false)
    }
  }, [])

  const fetchMessages = async () => {
    const fetchedMessages = await getMessagesByChatId(params.chatid as string)

    const imagePromises: Promise<MessageImage>[] = fetchedMessages.flatMap(
      message =>
        message.image_paths
          ? message.image_paths.map(async imagePath => {
              const url = await getMessageImageFromStorage(imagePath)

              if (url) {
                const response = await fetch(url)
                const blob = await response.blob()
                const base64 = await convertBlobToBase64(blob)

                return {
                  messageId: message.id,
                  path: imagePath,
                  base64,
                  url,
                  file: null
                }
              }

              return {
                messageId: message.id,
                path: imagePath,
                base64: "",
                url,
                file: null
              }
            })
          : []
    )

    const images: MessageImage[] = await Promise.all(imagePromises.flat())
    setChatImages(images)

    const messageFileItemPromises = fetchedMessages.map(
      async message => await getMessageFileItemsByMessageId(message.id)
    )

    const messageFileItems = await Promise.all(messageFileItemPromises)

    const uniqueFileItems = messageFileItems.flatMap(item => item.file_items)
    setChatFileItems(uniqueFileItems)

    const chatFiles = await getChatFilesByChatId(params.chatid as string)

    setChatFiles(
      chatFiles.files.map(file => ({
        id: file.id,
        name: file.name,
        type: file.type,
        file: null
      }))
    )

    setUseRetrieval(true)
    setShowFilesDisplay(true)

    const fetchedChatMessages = fetchedMessages.map(message => {
      return {
        message,
        fileItems: messageFileItems
          .filter(messageFileItem => messageFileItem.id === message.id)
          .flatMap(messageFileItem =>
            messageFileItem.file_items.map(fileItem => fileItem.id)
          )
      }
    })

    setChatMessages(fetchedChatMessages)
  }

  const fetchChat = async () => {
    const chat = await getChatById(params.chatid as string)
    if (!chat) return

    if (chat.assistant_id) {
      const assistant = assistants.find(
        assistant => assistant.id === chat.assistant_id
      )

      if (assistant) {
        setSelectedAssistant(assistant)

        const assistantTools = (
          await getAssistantToolsByAssistantId(assistant.id)
        ).tools
        setSelectedTools(assistantTools)
      }
    }

    setSelectedChat(chat)
    setChatSettings({
      model: chat.model as LLMID,
      prompt: chat.prompt,
      temperature: chat.temperature,
      contextLength: chat.context_length,
      includeProfileContext: chat.include_profile_context,
      includeWorkspaceInstructions: chat.include_workspace_instructions,
      embeddingsProvider: chat.embeddings_provider as "openai" | "local"
    })
  }

  if (loading) {
    return <Loading />
  }

  const showSplit = layoutReady && wide && documentPaneOpen && activeDocument !== null
  const showOverlay = layoutReady && !wide && documentPaneOpen && activeDocument !== null
  const closePane = () => setDocumentPaneOpen(false)

  return (
    <div ref={splitRef} className="chat-canvas relative flex h-full min-h-0 overflow-hidden">
      <div
        className="chat-rise relative flex h-full min-h-0 min-w-0 flex-col items-center overflow-hidden"
        style={showSplit ? { width: chatWidth, flex: "0 0 auto" } : { flex: "1 1 auto" }}
      >
        <div className="absolute right-4 top-3 z-20 flex h-10 items-center space-x-2">
          <ChatSecondaryButtons />
        </div>

        <div
          className="size-full min-h-0 overflow-y-auto overscroll-contain scroll-smooth"
          onScroll={handleScroll}
        >
          <div ref={messagesStartRef} />

          <ChatMessages />

          <div ref={messagesEndRef} className="h-28 sm:h-32" />
        </div>

        <div className="pointer-events-none absolute inset-x-0 bottom-0 z-10 bg-gradient-to-t from-[hsl(var(--chat-canvas))] via-[hsl(var(--chat-canvas)/0.96)] to-transparent px-3 pb-4 pt-8 sm:px-6 sm:pb-5">
          <div className="chat-rise-delay pointer-events-auto mx-auto w-full max-w-3xl">
            <ChatInput />
          </div>
        </div>
      </div>

      {showSplit && activeDocument ? (
        <>
          <div
            role="separator"
            aria-orientation="vertical"
            aria-label="Resize document"
            title="Drag to resize"
            onPointerDown={event => {
              event.preventDefault()
              setResizing(true)
            }}
            className="group relative z-20 w-2 shrink-0 cursor-col-resize"
          >
            <div
              className={
                resizing
                  ? "absolute inset-y-0 left-1/2 w-[2px] -translate-x-1/2 bg-foreground/50"
                  : "absolute inset-y-0 left-1/2 w-[2px] -translate-x-1/2 bg-transparent group-hover:bg-foreground/30"
              }
            />
          </div>
          <DocumentPane docx={activeDocument} onClose={closePane} />
        </>
      ) : null}

      {showOverlay && activeDocument ? (
        <div className="absolute inset-0 z-30">
          <DocumentPane docx={activeDocument} onClose={closePane} />
        </div>
      ) : null}
    </div>
  )
}

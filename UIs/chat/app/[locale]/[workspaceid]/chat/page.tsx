"use client"

import { useChatHandler } from "@/components/chat/chat-hooks/use-chat-handler"
import { ChatInput } from "@/components/chat/chat-input"
import { ChatUI } from "@/components/chat/chat-ui"
import { ChatbotUIContext } from "@/context/context"
import useHotkey from "@/lib/hooks/use-hotkey"
import { useContext } from "react"

export default function ChatPage() {
  useHotkey("o", () => handleNewChat())
  useHotkey("l", () => {
    handleFocusChatInput()
  })

  const { chatMessages } = useContext(ChatbotUIContext)

  const { handleNewChat, handleFocusChatInput } = useChatHandler()

  return (
    <>
      {chatMessages.length === 0 ? (
        <div className="chat-canvas chat-rise relative flex h-full min-h-0 flex-col items-center overflow-y-auto px-4">
          <div className="mx-auto flex w-full max-w-3xl flex-1 flex-col items-center justify-center pb-32 pt-16 text-center sm:pb-40">
            <div className="mb-6 flex size-20 items-center justify-center sm:size-24">
              <img
                src="/brand/Cognilance-Logo.png"
                alt="Cognilance"
                className="size-16 object-contain sm:size-20"
              />
            </div>

            <p className="mb-2 font-[family-name:var(--font-display)] text-[0.75rem] font-semibold uppercase tracking-[0.12em] text-muted-foreground">
              Cognilance
            </p>
            <h1 className="font-[family-name:var(--font-display)] text-2xl font-semibold tracking-tight text-foreground sm:text-3xl">
              What can we accomplish?
            </h1>
            <p className="mt-3 max-w-md text-sm leading-6 text-muted-foreground sm:text-base sm:leading-7">
              Think through a problem, coordinate specialized agents, or turn an
              idea into finished work.
            </p>
          </div>

          <div className="pointer-events-none absolute inset-x-0 bottom-0 z-10 bg-gradient-to-t from-[hsl(var(--chat-canvas))] via-[hsl(var(--chat-canvas)/0.96)] to-transparent px-3 pb-4 pt-12 sm:px-6 sm:pb-5">
            <div className="chat-rise-delay pointer-events-auto mx-auto w-full max-w-3xl">
              <ChatInput />
            </div>
          </div>
        </div>
      ) : (
        <ChatUI />
      )}
    </>
  )
}

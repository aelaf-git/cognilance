"use client"

import { ActivityStep } from "@/lib/coordinator-chat"
import { cn } from "@/lib/utils"
import { IconChevronRight, IconLoader2 } from "@tabler/icons-react"
import { FC, useEffect, useRef, useState } from "react"
import remarkGfm from "remark-gfm"
import { MessageMarkdownMemoized } from "./message-markdown-memoized"

const ThoughtText: FC<{ text: string }> = ({ text }) => (
  <MessageMarkdownMemoized
    className="max-w-none text-xs leading-5 text-muted-foreground [&_em]:text-foreground/80 [&_h1]:mb-1 [&_h1]:text-[13px] [&_h1]:font-medium [&_h1]:text-foreground [&_h2]:mb-1 [&_h2]:text-[13px] [&_h2]:font-medium [&_h2]:text-foreground [&_h3]:mb-1 [&_h3]:text-xs [&_h3]:font-medium [&_h3]:text-foreground [&_li]:my-0.5 [&_ol]:my-1.5 [&_ol]:list-decimal [&_ol]:pl-4 [&_p]:mb-2 [&_p:last-child]:mb-0 [&_strong]:font-medium [&_strong]:text-foreground [&_ul]:my-1.5 [&_ul]:list-disc [&_ul]:pl-4 [&_code]:rounded [&_code]:bg-muted/70 [&_code]:px-1 [&_code]:text-[11px]"
    remarkPlugins={[remarkGfm]}
  >
    {text}
  </MessageMarkdownMemoized>
)

interface ActivityTraceProps {
  steps: ActivityStep[]
}

export const ActivityTrace: FC<ActivityTraceProps> = ({ steps }) => {
  const rootStep = steps.find(step => step.id === "thinking") ?? steps[0]
  const childSteps = steps.filter(step => step.id !== rootStep?.id)
  const isThinking = rootStep?.label === "Thinking…"
  const latestChildId = childSteps[childSteps.length - 1]?.id
  const openedAfterDone = useRef(false)
  const userStepChoice = useRef<Record<string, boolean>>({})
  const [thoughtOpen, setThoughtOpen] = useState(isThinking)
  const [, setStepTick] = useState(0)

  useEffect(() => {
    if (isThinking) {
      openedAfterDone.current = false
      setThoughtOpen(true)
      return
    }
    userStepChoice.current = {}
    setStepTick(tick => tick + 1)
    if (!openedAfterDone.current) setThoughtOpen(false)
  }, [isThinking])

  if (!steps.length || !rootStep) return null

  const toggleThought = () => {
    if (!isThinking) openedAfterDone.current = true
    setThoughtOpen(prev => !prev)
  }

  const stepIsOpen = (id: string) => {
    if (Object.prototype.hasOwnProperty.call(userStepChoice.current, id)) {
      return userStepChoice.current[id]
    }
    return isThinking && id === latestChildId
  }

  const toggleStep = (id: string) => {
    userStepChoice.current[id] = !stepIsOpen(id)
    setStepTick(tick => tick + 1)
  }

  return (
    <div className="mb-1.5 w-full max-w-xl text-xs leading-5">
      <button
        type="button"
        className={cn(
          "flex items-center gap-1.5 py-0.5 text-left text-xs font-medium text-muted-foreground transition-colors hover:text-foreground focus-visible:outline-none focus-visible:text-foreground",
          thoughtOpen && "text-foreground/90"
        )}
        onClick={toggleThought}
        aria-expanded={thoughtOpen}
      >
        <IconChevronRight
          className={cn(
            "text-muted-foreground transition-transform",
            thoughtOpen && "rotate-90 text-foreground"
          )}
          size={13}
        />
        {isThinking && (
          <IconLoader2 className="animate-spin text-foreground" size={13} />
        )}
        <span>{rootStep.label}</span>
      </button>

      {thoughtOpen && (
        <div className="ml-1.5 mt-1 space-y-1 border-l border-border pl-4">
          {rootStep.detail && (
            <div className="py-0.5">
              <ThoughtText text={rootStep.detail} />
            </div>
          )}

          {childSteps.map(step => {
            const isOpen = stepIsOpen(step.id)
            const hasBody = Boolean(step.prompt || step.detail)
            return (
              <div key={step.id} className="space-y-0.5">
                <button
                  type="button"
                  className={cn(
                    "flex items-center gap-2 py-0.5 text-left text-xs leading-5 text-muted-foreground transition-all hover:text-foreground focus-visible:outline-none focus-visible:text-foreground",
                    isOpen && "pl-2 text-foreground/90"
                  )}
                  onClick={() => hasBody && toggleStep(step.id)}
                  aria-expanded={hasBody ? isOpen : undefined}
                >
                  <span
                    className={cn(
                      "size-1.5 shrink-0 rounded-full bg-muted-foreground/35",
                      isOpen && "bg-foreground",
                      step.status === "running" && "animate-pulse bg-foreground"
                    )}
                  />
                  <span>{step.label}</span>
                </button>

                {isOpen && hasBody && (
                  <div className="ml-3 max-h-72 space-y-1 overflow-auto border-l border-border py-0.5 pl-3 text-xs leading-5 text-muted-foreground">
                    {step.prompt && (
                      <div className="whitespace-pre-wrap">
                        <div className="text-muted-foreground/70">Prompt</div>
                        {step.prompt}
                      </div>
                    )}
                    {step.detail && <ThoughtText text={step.detail} />}
                  </div>
                )}
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}

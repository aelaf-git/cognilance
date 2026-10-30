"use client"

import { ActivityStep } from "@/lib/coordinator-chat"
import { cn } from "@/lib/utils"
import { IconChevronRight, IconLoader2 } from "@tabler/icons-react"
import { FC, useState } from "react"

interface ActivityTraceProps {
  steps: ActivityStep[]
}

export const ActivityTrace: FC<ActivityTraceProps> = ({ steps }) => {
  const [thoughtOpen, setThoughtOpen] = useState(false)
  const [openStepIds, setOpenStepIds] = useState<Record<string, boolean>>({})

  if (!steps.length) return null

  const rootStep = steps.find(step => step.id === "thinking") ?? steps[0]
  const childSteps = steps.filter(step => step.id !== rootStep.id)
  const isThinking = rootStep.label === "Thinking…"

  const toggleStep = (id: string) => {
    setOpenStepIds(prev => ({
      ...prev,
      [id]: !prev[id]
    }))
  }

  return (
    <div className="mb-1.5 w-full max-w-xl text-xs leading-5">
      <button
        type="button"
        className={cn(
          "flex items-center gap-1.5 py-0.5 text-left text-xs font-medium text-muted-foreground transition-colors hover:text-foreground focus-visible:outline-none focus-visible:text-foreground",
          thoughtOpen && "text-foreground/90"
        )}
        onClick={() => setThoughtOpen(prev => !prev)}
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
          <div className="py-0.5 text-xs leading-5 text-muted-foreground whitespace-pre-wrap">
            {rootStep.detail}
          </div>

          {childSteps.map(step => {
              const isOpen = !!openStepIds[step.id]
              return (
                <div key={step.id} className="space-y-0.5">
                  <button
                    type="button"
                    className={cn(
                      "flex items-center gap-2 py-0.5 text-left text-xs leading-5 text-muted-foreground transition-all hover:text-foreground focus-visible:outline-none focus-visible:text-foreground",
                      isOpen && "pl-2 text-foreground/90"
                    )}
                    onClick={() => toggleStep(step.id)}
                    aria-expanded={isOpen}
                  >
                    <span
                      className={cn(
                        "size-1.5 shrink-0 rounded-full bg-muted-foreground/35",
                        isOpen && "bg-foreground"
                      )}
                    />
                    <span>{step.label}</span>
                  </button>

                  {isOpen && (
                    <div className="ml-3 border-l border-border py-0.5 pl-3 text-xs leading-5 text-muted-foreground whitespace-pre-wrap">
                      {step.detail}
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

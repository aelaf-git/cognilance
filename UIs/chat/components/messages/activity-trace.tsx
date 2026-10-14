"use client"

import { ActivityStep } from "@/lib/orchestrator-chat"
import { FC, useState } from "react"

interface ActivityTraceProps {
  steps: ActivityStep[]
}

export const ActivityTrace: FC<ActivityTraceProps> = ({ steps }) => {
  const [openId, setOpenId] = useState<string | null>(null)

  return (
    <div className="mb-3 space-y-1">
      {steps.map(step => {
        const open = openId === step.id
        return (
          <button
            key={step.id}
            type="button"
            className="block w-full text-left text-xs leading-5 text-muted-foreground hover:text-foreground"
            onClick={() => setOpenId(open ? null : step.id)}
          >
            <div>{step.label}</div>
            {open && (
              <div className="text-xs leading-5 text-muted-foreground">
                {step.detail}
              </div>
            )}
          </button>
        )
      })}
    </div>
  )
}

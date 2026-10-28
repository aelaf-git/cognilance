import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle
} from "@/components/ui/card"
import { FC, useRef } from "react"

export const SETUP_STEP_COUNT = 3

interface StepContainerProps {
  stepDescription: string
  stepNum: number
  stepTitle: string
  onShouldProceed: (shouldProceed: boolean) => void
  children?: React.ReactNode
  showBackButton?: boolean
  showNextButton?: boolean
}

export const StepContainer: FC<StepContainerProps> = ({
  stepDescription,
  stepNum,
  stepTitle,
  onShouldProceed,
  children,
  showBackButton = false,
  showNextButton = true
}) => {
  const buttonRef = useRef<HTMLButtonElement>(null)

  const handleKeyDown = (e: React.KeyboardEvent<HTMLDivElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      if (buttonRef.current) {
        buttonRef.current.click()
      }
    }
  }

  return (
    <Card
      className="max-h-[calc(100vh-60px)] w-[min(600px,calc(100vw-2rem))] overflow-auto rounded-[16px] border-border bg-card shadow-none"
      onKeyDown={handleKeyDown}
    >
      <CardHeader>
        <CardTitle className="font-[family-name:var(--font-display)] flex justify-between text-xl tracking-tight">
          <div>{stepTitle}</div>

          <div className="text-sm font-normal text-muted-foreground">
            {stepNum} / {SETUP_STEP_COUNT}
          </div>
        </CardTitle>

        <CardDescription className="text-muted-foreground">
          {stepDescription}
        </CardDescription>
      </CardHeader>

      <CardContent className="space-y-4">{children}</CardContent>

      <CardFooter className="flex justify-between border-t border-border pt-6">
        <div>
          {showBackButton && (
            <Button
              size="sm"
              variant="outline"
              onClick={() => onShouldProceed(false)}
            >
              Back
            </Button>
          )}
        </div>

        <div>
          {showNextButton && (
            <Button
              ref={buttonRef}
              size="sm"
              onClick={() => onShouldProceed(true)}
            >
              Next
            </Button>
          )}
        </div>
      </CardFooter>
    </Card>
  )
}

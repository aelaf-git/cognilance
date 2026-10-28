import { IconLoader2 } from "@tabler/icons-react"

export default function Loading() {
  return (
    <div className="chat-canvas flex size-full flex-col items-center justify-center gap-3">
      <IconLoader2 className="size-10 animate-spin text-muted-foreground" />
      <p className="font-[family-name:var(--font-display)] text-sm text-muted-foreground">
        Loading
      </p>
    </div>
  )
}

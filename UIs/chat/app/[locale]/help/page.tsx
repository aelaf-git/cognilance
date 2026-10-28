import { Brand } from "@/components/ui/brand"

export default function HelpPage() {
  return (
    <div className="chat-canvas flex size-full flex-col items-center justify-center gap-6 px-6 text-center">
      <Brand />
      <div className="max-w-md space-y-2">
        <h1 className="font-[family-name:var(--font-display)] text-2xl font-semibold tracking-tight text-foreground">
          Help
        </h1>
        <p className="text-sm leading-6 text-muted-foreground">
          Help docs are under construction. For now, use the chat to ask
          Cognilance, or contact the team from the marketing site.
        </p>
      </div>
    </div>
  )
}

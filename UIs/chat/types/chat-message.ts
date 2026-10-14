import { ActivityStep } from "@/lib/orchestrator-chat"
import { Tables } from "@/supabase/types"

export interface ChatMessage {
  message: Tables<"messages">
  fileItems: string[]
  activity?: ActivityStep[]
}

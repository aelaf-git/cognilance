import { ActivityStep } from "@/lib/coordinator-chat"
import { Tables } from "@/supabase/types"

export interface ChatMessage {
  message: Tables<"messages">
  fileItems: string[]
  activity?: ActivityStep[]
}

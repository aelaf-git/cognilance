import { ActivityStep } from "@/lib/coordinator-chat"
import { DocxDocument } from "@/lib/docx-document"
import { Tables } from "@/supabase/types"

export interface ChatMessage {
  message: Tables<"messages">
  fileItems: string[]
  activity?: ActivityStep[]
  document?: DocxDocument
}

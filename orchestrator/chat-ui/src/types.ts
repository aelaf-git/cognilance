export type StepStatus = "pending" | "running" | "done" | "fallback";

export type FeedCardType =
  | "user"
  | "registry"
  | "planner"
  | "routing"
  | "delegation"
  | "agent-exec"
  | "output"
  | "gen-ui";

export type SubtaskItem = {
  id: string;
  title: string;
  assignee?: string;
  skill?: string | null;
  tool?: string | null;
  instruction?: string;
  detail?: string;
  status: StepStatus;
  result?: string;
  toolLabel?: string;
};

export type CatalogAgent = {
  name: string;
  online: boolean;
  skills: string[];
  url?: string | null;
  price_usd_cents?: number;
  payout_wallet?: string | null;
};

export type FeedCard = {
  id: string;
  type: FeedCardType;
  title: string;
  status: StepStatus;
  content?: string;
  thinking?: string;
  mono?: boolean;
  route?: string;
  complexity?: string;
  subtasks?: SubtaskItem[];
  catalogAgents?: CatalogAgent[];
  uiComponent?: string | null;
  uiProps?: Record<string, unknown>;
};

export type OrchestrationTurn = {
  id: string;
  sessionId?: string;
  missionId?: string;
  cards: FeedCard[];
};

export type ChatMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
  streaming?: boolean;
  error?: boolean;
  sessionId?: string;
  ui?: UiItem | null;
};

export type ConversationSummary = {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
  session_count?: number;
  latest_status?: string | null;
  active_listeners?: SubscriptionSummary[];
};

export type SubscriptionSummary = {
  id: string;
  integration: string;
  kind: string;
  status: string;
  poll_interval_seconds?: number;
};

export type SessionSummary = {
  id: string;
  session_id?: string;
  instruction: string;
  status: string;
  session_type: "once" | "recurring";
  thread_id: string;
  conversation_id?: string;
  created_at: string;
  result_text?: string | null;
  error?: string | null;
  subscription_id?: string | null;
  listener_active?: boolean;
  listener_integration?: string;
  listener_kind?: string;
  display_status?: string;
};

export type UiItem = {
  name: string;
  props: Record<string, unknown>;
};

export type AppIntegration = {
  id: string;
  name: string;
  description: string;
  logo?: string;
  category?: string;
  connected: boolean;
  coming_soon?: boolean;
  auth_type?: string;
  actions?: string[];
};

export const CARD_META: Record<
  FeedCardType,
  { label: string; accent: string; accentClass: string }
> = {
  user: { label: "User Prompt", accent: "#ffffff", accentClass: "border-l-white/30" },
  registry: {
    label: "Marketplace Lookup",
    accent: "#14b8a6",
    accentClass: "border-l-registry",
  },
  planner: { label: "Thinking & Plan", accent: "#3b82f6", accentClass: "border-l-planner" },
  routing: { label: "Routing", accent: "#a855f7", accentClass: "border-l-thinking" },
  delegation: { label: "Delegation", accent: "#f97316", accentClass: "border-l-task" },
  "agent-exec": {
    label: "Hired Agents",
    accent: "#14b8a6",
    accentClass: "border-l-registry",
  },
  output: { label: "Aggregated Output", accent: "#e5e5e5", accentClass: "border-l-white/20" },
  "gen-ui": { label: "Gen UI Selection", accent: "#22c55e", accentClass: "border-l-genui" },
};

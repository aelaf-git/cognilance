import type {
  FeedCard,
  FeedCardType,
  OrchestrationTurn,
  StepStatus,
  SubtaskItem,
  UiItem,
} from "@/types";
import { CARD_META } from "@/types";

export const PROCESS_CARD_TYPES: FeedCardType[] = [
  "planner",
  "routing",
  "delegation",
  "agent-exec",
  "gen-ui",
];

function uid() {
  return crypto.randomUUID();
}

export function makeCard(type: FeedCardType, partial: Partial<FeedCard> = {}): FeedCard {
  return {
    id: uid(),
    type,
    title: CARD_META[type].label,
    status: "pending",
    ...partial,
  };
}

function updateCard(
  turn: OrchestrationTurn,
  type: FeedCardType,
  patch: Partial<FeedCard>,
): OrchestrationTurn {
  return {
    ...turn,
    cards: turn.cards.map((c) => (c.type === type ? { ...c, ...patch } : c)),
  };
}

function ensureCard(turn: OrchestrationTurn, type: FeedCardType): OrchestrationTurn {
  if (turn.cards.some((c) => c.type === type)) return turn;
  return { ...turn, cards: [...turn.cards, makeCard(type, { status: "running" })] };
}

export type EventContext = {
  route?: string;
  subtasks: SubtaskItem[];
  answer: string;
  uiItems: UiItem[];
};

export function createEventContext(): EventContext {
  return { subtasks: [], answer: "", uiItems: [] };
}

export function applySessionEvent(
  turn: OrchestrationTurn,
  data: Record<string, unknown>,
  ctx: EventContext,
): OrchestrationTurn {
  const event = data.event as string;

  if (event === "thinking" && data.delta) {
    const content =
      (turn.cards.find((c) => c.type === "planner")?.content ?? "") + String(data.delta);
    return updateCard(turn, "planner", { status: "running", content });
  }
  if (event === "thinking_done") {
    return updateCard(turn, "planner", { status: "done" });
  }
  if (event === "plan" && data.data) {
    const plan = data.data as Record<string, unknown>;
    ctx.route = (plan.route as string) ?? ctx.route;
    const steps = (plan.steps as { title: string; detail: string }[]) ?? [];
    const rawSubtasks = (plan.subtasks as SubtaskItem[]) ?? [];
    ctx.subtasks = rawSubtasks.map((s) => ({ ...s, status: "pending" as StepStatus }));
    const reasoning = (plan.reasoning as string) ?? "";
    const thinking = (plan.thinking as string) ?? "";
    const planText = [
      reasoning && `Reasoning:\n${reasoning}`,
      steps.length
        ? `Steps:\n${steps.map((s, i) => `${i + 1}. ${s.title}\n   ${s.detail}`).join("\n")}`
        : "",
      thinking && `Thinking:\n${thinking}`,
    ]
      .filter(Boolean)
      .join("\n\n");
    return updateCard(turn, "planner", {
      status: "done",
      content: planText || turn.cards.find((c) => c.type === "planner")?.content,
    });
  }
  if (event === "route_decision") {
    ctx.route = (data.route as string) ?? ctx.route;
    const complexity = data.complexity as string | undefined;
    let next = ensureCard(turn, "routing");
    return updateCard(next, "routing", {
      status: "done",
      route: ctx.route,
      complexity,
      content: `Route: ${ctx.route}${complexity ? `\nComplexity: ${complexity}` : ""}`,
    });
  }
  if (event === "execution_start") {
    let next = ensureCard(turn, "delegation");
    next = updateCard(next, "delegation", {
      status: "running",
      subtasks: ctx.subtasks.length
        ? ctx.subtasks
        : [{ id: "direct", title: "Direct execution", status: "pending" }],
      content:
        ctx.route === "simple"
          ? "Simple route — thinking agent will answer directly."
          : `Delegating ${ctx.subtasks.length || 1} subtask(s).`,
    });
    return ensureCard(next, "agent-exec");
  }
  if (event === "subtask_start") {
    const id = data.id as string;
    const title = data.title as string;
    const assignee = data.assignee as string;
    let next = ensureCard(turn, "agent-exec");
    const existing = next.cards.find((c) => c.type === "agent-exec");
    const list = [...(existing?.subtasks ?? ctx.subtasks)];
    const idx = list.findIndex((s) => s.id === id);
    const item: SubtaskItem = { id, title, assignee, status: "running" };
    if (idx >= 0) list[idx] = { ...list[idx], ...item, status: "running" };
    else list.push(item);
    ctx.subtasks = list;
    return updateCard(next, "agent-exec", { status: "running", subtasks: list });
  }
  if (event === "subtask_done") {
    const id = data.id as string;
    const assignee = data.assignee as string;
    const st = data.status as string;
    const isFallback = assignee === "thinking";
    let next = ensureCard(turn, "agent-exec");
    const card = next.cards.find((c) => c.type === "agent-exec");
    const list = (card?.subtasks ?? ctx.subtasks).map((s) =>
      s.id === id
        ? {
            ...s,
            status: (isFallback ? "fallback" : st === "failed" ? "fallback" : "done") as StepStatus,
            assignee,
          }
        : s,
    );
    const allDone = list.every((s) => s.status === "done" || s.status === "fallback");
    next = updateCard(next, "agent-exec", {
      status: allDone ? "done" : "running",
      subtasks: list,
    });
    return updateCard(next, "delegation", { status: "done" });
  }
  if (event === "execution_done") {
    let next = updateCard(turn, "delegation", { status: "done" });
    const exec = next.cards.find((c) => c.type === "agent-exec");
    if (!exec) {
      next = ensureCard(next, "agent-exec");
      next = updateCard(next, "agent-exec", {
        status: "done",
        content: ctx.route === "simple" ? "Handled by thinking agent." : undefined,
      });
    }
    return next;
  }
  if (event === "tool_start" || event === "tool_done") {
    return turn;
  }
  if (event === "ui" && data.name !== "text-card") {
    ctx.uiItems.push({
      name: data.name as string,
      props: (data.props as Record<string, unknown>) ?? {},
    });
    let next = ensureCard(turn, "gen-ui");
    return updateCard(next, "gen-ui", {
      status: "running",
      uiComponent: data.name as string,
      uiProps: (data.props as Record<string, unknown>) ?? {},
    });
  }
  if (event === "gen_ui_selected") {
    const component = data.component as string | null | undefined;
    if (component) {
      const props = (data.props as Record<string, unknown>) ?? {};
      ctx.uiItems.push({ name: component, props });
      let next = ensureCard(turn, "gen-ui");
      return updateCard(next, "gen-ui", {
        status: "done",
        uiComponent: component,
        uiProps: props,
      });
    }
    let next = ensureCard(turn, "gen-ui");
    return updateCard(next, "gen-ui", {
      status: "done",
      uiComponent: null,
      content: String(data.reason ?? "Plain text response."),
    });
  }
  if (event === "answer" && data.delta) {
    ctx.answer += String(data.delta);
    return turn;
  }
  if (event === "answer_done") {
    if (data.text) ctx.answer = String(data.text);
    return turn;
  }
  if (event === "final") {
    if (!ctx.answer && data.text) ctx.answer = String(data.text);
    const finalUi = (data.ui as UiItem[]) ?? [];
    for (const item of finalUi) {
      if (item.name !== "text-card") ctx.uiItems.push(item);
    }
    let next = turn;
    next = ensureCard(next, "gen-ui");
    const lastUi = ctx.uiItems[ctx.uiItems.length - 1];
    return updateCard(next, "gen-ui", {
      status: "done",
      uiComponent: lastUi?.name ?? null,
      uiProps: lastUi?.props ?? {},
      content: lastUi ? undefined : "No rich UI component selected.",
    });
  }
  if (event === "error") {
    return {
      ...turn,
      cards: [
        ...turn.cards,
        makeCard("output", {
          status: "fallback",
          content: String(data.message ?? "Request failed"),
          mono: true,
        }),
      ],
    };
  }
  return turn;
}

export function finalizeSessionTurn(turn: OrchestrationTurn, ctx: EventContext): OrchestrationTurn {
  let next = turn;
  if (!next.cards.some((c) => c.type === "routing") && ctx.route) {
    next = ensureCard(next, "routing");
    next = updateCard(next, "routing", { status: "done", route: ctx.route });
  }
  if (!next.cards.some((c) => c.type === "gen-ui") && ctx.uiItems.length) {
    next = ensureCard(next, "gen-ui");
    const lastUi = ctx.uiItems[ctx.uiItems.length - 1];
    next = updateCard(next, "gen-ui", {
      status: "done",
      uiComponent: lastUi?.name ?? null,
      uiProps: lastUi?.props ?? {},
    });
  }
  return next;
}

export function extractChatOutput(
  content: string,
  data: Record<string, unknown>,
  ctx: EventContext,
): string {
  const event = data.event as string;
  if (event === "answer" && data.delta) return content + String(data.delta);
  if (event === "answer_done" && data.text) return String(data.text);
  if (event === "final" && data.text) return String(data.text) || ctx.answer;
  if (event === "error") return String(data.message ?? "Request failed");
  return content;
}

export function isOutputEvent(event: string): boolean {
  return event === "answer" || event === "answer_done" || event === "final" || event === "error";
}

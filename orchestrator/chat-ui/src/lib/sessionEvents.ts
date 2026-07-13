import type {
  CatalogAgent,
  FeedCard,
  FeedCardType,
  OrchestrationTurn,
  StepStatus,
  SubtaskItem,
  UiItem,
} from "@/types";
import { CARD_META } from "@/types";

export const PROCESS_CARD_TYPES: FeedCardType[] = [
  "registry",
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

function parseHireSkill(tool?: string | null, skill?: string | null): string | null {
  if (skill) return skill;
  if (tool?.startsWith("hire:")) return tool.slice(5);
  return null;
}

function normalizeSubtask(raw: Partial<SubtaskItem> & { id: string }): SubtaskItem {
  const tool = raw.tool ?? null;
  const skill = parseHireSkill(tool, raw.skill ?? null);
  return {
    id: raw.id,
    title: raw.title || "Task",
    assignee: raw.assignee,
    skill,
    tool,
    instruction: raw.instruction,
    detail: raw.detail,
    status: raw.status ?? "pending",
    result: raw.result,
    toolLabel: raw.toolLabel,
  };
}

export type EventContext = {
  route?: string;
  subtasks: SubtaskItem[];
  answer: string;
  uiItems: UiItem[];
  activeSubtaskId?: string;
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

  if (event === "catalog") {
    const agents = (data.agents as CatalogAgent[] | undefined) ?? [];
    const onlineCount = Number(data.online_count ?? agents.filter((a) => a.online).length);
    const totalCount = Number(data.total_count ?? agents.length);
    const summary =
      totalCount === 0
        ? "Registry queried — no marketplace agents registered."
        : `Registry queried — ${onlineCount} online / ${totalCount} total.`;
    let next = ensureCard(turn, "registry");
    return updateCard(next, "registry", {
      status: "done",
      catalogAgents: agents,
      content: summary,
    });
  }
  if (event === "thinking" && data.delta) {
    const thinking =
      (turn.cards.find((c) => c.type === "planner")?.thinking ?? "") + String(data.delta);
    return updateCard(turn, "planner", { status: "running", thinking });
  }
  if (event === "thinking_done") {
    const planner = turn.cards.find((c) => c.type === "planner");
    const streamed = planner?.thinking ?? "";
    const finalText = data.text ? String(data.text) : streamed;
    return updateCard(turn, "planner", {
      status: planner?.content ? "done" : "running",
      thinking: finalText || streamed,
    });
  }
  if (event === "plan" && data.data) {
    const plan = data.data as Record<string, unknown>;
    ctx.route = (plan.route as string) ?? ctx.route;
    const steps = (plan.steps as { title: string; detail: string }[]) ?? [];
    const rawSubtasks = (plan.subtasks as Partial<SubtaskItem>[]) ?? [];
    ctx.subtasks = rawSubtasks.map((s) =>
      normalizeSubtask({
        ...s,
        id: String(s.id || uid()),
        status: "pending",
      }),
    );
    const reasoning = (plan.reasoning as string) ?? "";
    const planThinking = (plan.thinking as string) ?? "";
    const existingThinking = turn.cards.find((c) => c.type === "planner")?.thinking ?? "";
    const planText = [
      reasoning && `Reasoning:\n${reasoning}`,
      steps.length
        ? `Steps:\n${steps.map((s, i) => `${i + 1}. ${s.title}\n   ${s.detail}`).join("\n")}`
        : "",
    ]
      .filter(Boolean)
      .join("\n\n");
    return updateCard(turn, "planner", {
      status: "done",
      thinking: existingThinking || planThinking || undefined,
      content: planText || undefined,
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
          : `Delegating ${ctx.subtasks.length || 1} subtask(s) to specialists.`,
    });
    return ensureCard(next, "agent-exec");
  }
  if (event === "subtask_start") {
    const id = String(data.id ?? "");
    const title = String(data.title ?? "Task");
    const assignee = data.assignee ? String(data.assignee) : undefined;
    const tool = data.tool ? String(data.tool) : undefined;
    const skill = parseHireSkill(tool, data.skill ? String(data.skill) : null);
    const instruction = data.instruction ? String(data.instruction) : undefined;
    ctx.activeSubtaskId = id;
    let next = ensureCard(turn, "agent-exec");
    const existing = next.cards.find((c) => c.type === "agent-exec");
    const list = [...(existing?.subtasks ?? ctx.subtasks)];
    const idx = list.findIndex((s) => s.id === id);
    const item = normalizeSubtask({
      ...(idx >= 0 ? list[idx] : {}),
      id,
      title,
      assignee,
      tool: tool ?? (idx >= 0 ? list[idx].tool : null),
      skill,
      instruction: instruction ?? (idx >= 0 ? list[idx].instruction : undefined),
      status: "running",
    });
    if (idx >= 0) list[idx] = { ...list[idx], ...item };
    else list.push(item);
    ctx.subtasks = list;
    return updateCard(next, "agent-exec", { status: "running", subtasks: list });
  }
  if (event === "subtask_done") {
    const id = String(data.id ?? "");
    const assignee = data.assignee ? String(data.assignee) : undefined;
    const st = data.status as string;
    const isFallback = assignee === "thinking" || st === "fallback";
    const resultText = data.text ? String(data.text) : undefined;
    let next = ensureCard(turn, "agent-exec");
    const card = next.cards.find((c) => c.type === "agent-exec");
    const list = (card?.subtasks ?? ctx.subtasks).map((s) =>
      s.id === id
        ? {
            ...s,
            status: (isFallback ? "fallback" : st === "failed" ? "fallback" : "done") as StepStatus,
            assignee: assignee ?? s.assignee,
            result: resultText ?? s.result,
          }
        : s,
    );
    ctx.subtasks = list;
    if (ctx.activeSubtaskId === id) ctx.activeSubtaskId = undefined;
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
  if (event === "tool_start") {
    const tool = String(data.tool ?? "");
    const assignee = data.assignee ? String(data.assignee) : undefined;
    let next = ensureCard(turn, "agent-exec");
    const card = next.cards.find((c) => c.type === "agent-exec");
    const list = [...(card?.subtasks ?? ctx.subtasks)];
    const targetIdx =
      list.findIndex((s) => s.status === "running") >= 0
        ? list.findIndex((s) => s.status === "running")
        : list.findIndex((s) => s.assignee === assignee);
    if (targetIdx >= 0) {
      list[targetIdx] = {
        ...list[targetIdx],
        tool: tool || list[targetIdx].tool,
        skill: parseHireSkill(tool, list[targetIdx].skill),
        assignee: assignee ?? list[targetIdx].assignee,
        toolLabel: tool || list[targetIdx].toolLabel,
        status: "running",
      };
      ctx.subtasks = list;
      return updateCard(next, "agent-exec", { status: "running", subtasks: list });
    }
    if (tool || assignee) {
      list.push(
        normalizeSubtask({
          id: uid(),
          title: tool.startsWith("hire:")
            ? `Hire ${assignee || tool.slice(5)}`
            : tool || "Tool call",
          assignee,
          tool,
          skill: parseHireSkill(tool, null),
          toolLabel: tool,
          status: "running",
        }),
      );
      ctx.subtasks = list;
      return updateCard(next, "agent-exec", { status: "running", subtasks: list });
    }
    return next;
  }
  if (event === "tool_done") {
    const tool = String(data.tool ?? "");
    const assignee = data.assignee ? String(data.assignee) : undefined;
    const st = String(data.status ?? "completed");
    let next = ensureCard(turn, "agent-exec");
    const card = next.cards.find((c) => c.type === "agent-exec");
    const list = (card?.subtasks ?? ctx.subtasks).map((s) => {
      const matches =
        (tool && (s.tool === tool || s.toolLabel === tool)) ||
        (assignee && s.assignee === assignee && s.status === "running");
      if (!matches) return s;
      return {
        ...s,
        toolLabel: tool || s.toolLabel,
        assignee: assignee ?? s.assignee,
        status: (st === "fallback" || st === "failed" ? "fallback" : s.status === "pending" ? "done" : s.status) as StepStatus,
      };
    });
    ctx.subtasks = list;
    return updateCard(next, "agent-exec", { subtasks: list });
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

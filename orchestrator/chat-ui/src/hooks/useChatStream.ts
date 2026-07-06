import { useCallback, useRef, useState } from "react";
import type {
  FeedCard,
  FeedCardType,
  OrchestrationTurn,
  StepStatus,
  SubtaskItem,
  UiItem,
} from "@/types";
import { CARD_META } from "@/types";

const THREAD_KEY = "cognilance_orchestrator_thread";

function uid() {
  return crypto.randomUUID();
}

function makeCard(type: FeedCardType, partial: Partial<FeedCard> = {}): FeedCard {
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

type EventContext = {
  route?: string;
  subtasks: SubtaskItem[];
  answer: string;
  uiItems: UiItem[];
};

function applyEvent(
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
      subtasks: undefined,
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
  if (event === "answer" && data.delta) {
    ctx.answer += String(data.delta);
    let next = turn;
    if (ctx.route === "simple") {
      next = ensureCard(next, "delegation");
      next = updateCard(next, "delegation", {
        status: "done",
        content: "Simple route — thinking agent answering directly.",
      });
      next = ensureCard(next, "agent-exec");
      next = updateCard(next, "agent-exec", {
        status: "running",
        subtasks: [
          { id: "thinking", title: "Direct answer", assignee: "thinking", status: "running" },
        ],
      });
    }
    next = ensureCard(next, "output");
    return updateCard(next, "output", { status: "running", content: ctx.answer, mono: false });
  }
  if (event === "answer_done") {
    let next = ensureCard(turn, "output");
    next = updateCard(next, "output", {
      status: "done",
      content: (data.text as string) || ctx.answer,
    });
    if (ctx.route === "simple") {
      next = ensureCard(next, "agent-exec");
      next = updateCard(next, "agent-exec", {
        status: "done",
        subtasks: [
          { id: "thinking", title: "Direct answer", assignee: "thinking", status: "done" },
        ],
      });
    }
    return next;
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
  if (event === "final") {
    if (!ctx.answer && data.text) ctx.answer = String(data.text);
    const finalUi = (data.ui as UiItem[]) ?? [];
    for (const item of finalUi) {
      if (item.name !== "text-card") ctx.uiItems.push(item);
    }
    let next = turn;
    if (ctx.answer) {
      next = ensureCard(next, "output");
      next = updateCard(next, "output", { status: "done", content: ctx.answer });
    }
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

function finalizeTurn(turn: OrchestrationTurn, ctx: EventContext): OrchestrationTurn {
  let next = turn;
  if (!next.cards.some((c) => c.type === "routing") && ctx.route) {
    next = ensureCard(next, "routing");
    next = updateCard(next, "routing", { status: "done", route: ctx.route });
  }
  if (ctx.route === "simple" && !next.cards.some((c) => c.type === "delegation")) {
    next = ensureCard(next, "delegation");
    next = updateCard(next, "delegation", {
      status: "done",
      content: "Simple route — no specialist delegation.",
    });
  }
  if (ctx.answer && !next.cards.some((c) => c.type === "output")) {
    next = ensureCard(next, "output");
    next = updateCard(next, "output", { status: "done", content: ctx.answer });
  }
  if (!next.cards.some((c) => c.type === "gen-ui")) {
    next = ensureCard(next, "gen-ui");
    const lastUi = ctx.uiItems[ctx.uiItems.length - 1];
    next = updateCard(next, "gen-ui", {
      status: "done",
      uiComponent: lastUi?.name ?? null,
      uiProps: lastUi?.props ?? {},
      content: lastUi ? undefined : "Plain text response.",
    });
  }
  return next;
}

export function useChatStream(onMissionUpdate?: () => void) {
  const [turns, setTurns] = useState<OrchestrationTurn[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);
  const threadIdRef = useRef(localStorage.getItem(THREAD_KEY) ?? "");
  const activeMissionRef = useRef<string | null>(null);

  const processStream = useCallback(
    async (
      body: ReadableStream<Uint8Array>,
      turnId: string,
      missionId: string | null,
    ) => {
      const ctx: EventContext = { subtasks: [], answer: "", uiItems: [] };
      const reader = body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const parts = buffer.split("\n\n");
        buffer = parts.pop() ?? "";

        for (const part of parts) {
          const line = part.trim();
          if (!line.startsWith("data: ")) continue;
          let data: Record<string, unknown>;
          try {
            data = JSON.parse(line.slice(6));
          } catch {
            continue;
          }

          const event = data.event as string;
          if (event === "mission_created") {
            activeMissionRef.current = String(data.mission_id);
          }
          if (event === "status" && data.message) {
            setStatusMessage(String(data.message));
          }
          if (data.thread_id) {
            threadIdRef.current = String(data.thread_id);
            localStorage.setItem(THREAD_KEY, threadIdRef.current);
          }

          setTurns((prev) =>
            prev.map((t) => {
              if (t.id !== turnId) return t;
              const updated = applyEvent(t, data, ctx);
              return missionId ? { ...updated, missionId } : updated;
            }),
          );
        }
      }

      setTurns((prev) =>
        prev.map((t) => (t.id === turnId ? finalizeTurn(t, ctx) : t)),
      );
    },
    [],
  );

  const send = useCallback(
    async (text: string) => {
      const turnId = uid();
      const turn: OrchestrationTurn = {
        id: turnId,
        cards: [
          makeCard("user", { status: "done", content: text }),
          makeCard("planner", { status: "running", content: "" }),
        ],
      };
      setTurns((prev) => [...prev, turn]);
      setIsStreaming(true);
      setStatusMessage("Planning…");
      activeMissionRef.current = null;

      try {
        const res = await fetch("/chat/stream", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            text,
            thread_id: threadIdRef.current || null,
          }),
        });
        if (!res.ok || !res.body) throw new Error("Stream request failed");
        const missionHeader = res.headers.get("X-Mission-Id");
        await processStream(res.body, turnId, missionHeader);
      } catch (err) {
        setTurns((prev) =>
          prev.map((t) =>
            t.id === turnId
              ? {
                  ...t,
                  cards: [
                    ...t.cards,
                    makeCard("output", {
                      status: "fallback",
                      content: err instanceof Error ? err.message : String(err),
                      mono: true,
                    }),
                  ],
                }
              : t,
          ),
        );
      } finally {
        setIsStreaming(false);
        setStatusMessage(null);
        onMissionUpdate?.();
      }
    },
    [onMissionUpdate, processStream],
  );

  const reconnectMission = useCallback(
    async (missionId: string) => {
      const turnId = uid();
      setTurns((prev) => [
        ...prev,
        {
          id: turnId,
          missionId,
          cards: [makeCard("planner", { status: "running", content: "Reconnecting to mission…" })],
        },
      ]);
      setIsStreaming(true);
      try {
        const res = await fetch(`/missions/${missionId}/events`);
        if (!res.ok || !res.body) throw new Error("Could not reconnect to mission");
        await processStream(res.body, turnId, missionId);
      } catch (err) {
        setTurns((prev) =>
          prev.map((t) =>
            t.id === turnId
              ? {
                  ...t,
                  cards: [
                    makeCard("output", {
                      status: "fallback",
                      content: err instanceof Error ? err.message : String(err),
                      mono: true,
                    }),
                  ],
                }
              : t,
          ),
        );
      } finally {
        setIsStreaming(false);
        onMissionUpdate?.();
      }
    },
    [onMissionUpdate, processStream],
  );

  return {
    turns,
    send,
    reconnectMission,
    isStreaming,
    statusMessage,
    activeMissionId: activeMissionRef.current,
  };
}

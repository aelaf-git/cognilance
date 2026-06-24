import { useCallback, useRef, useState } from "react";
import type {
  FeedCard,
  FeedCardType,
  HiredAgent,
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

function isSpecialist(name: string | undefined): name is string {
  return Boolean(name && name !== "thinking");
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

export function useChatStream() {
  const [turns, setTurns] = useState<OrchestrationTurn[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);
  const [hiredAgents, setHiredAgents] = useState<HiredAgent[]>([]);
  const threadIdRef = useRef(localStorage.getItem(THREAD_KEY) ?? "");
  /** subtask id → specialist name tentatively hired on subtask_start */
  const pendingHiresRef = useRef<Map<string, string>>(new Map());
  /** specialist name → number of in-flight subtasks */
  const activeCountRef = useRef<Map<string, number>>(new Map());

  const resetHiredAgents = useCallback(() => {
    setHiredAgents([]);
    pendingHiresRef.current = new Map();
    activeCountRef.current = new Map();
  }, []);

  const upsertHired = useCallback((name: string, patch: Partial<HiredAgent>) => {
    setHiredAgents((prev) => {
      const idx = prev.findIndex((a) => a.name === name);
      if (idx >= 0) {
        const next = [...prev];
        next[idx] = { ...next[idx], ...patch, name };
        return next;
      }
      return [...prev, { name, runStatus: "idle", ...patch }];
    });
  }, []);

  const removeHired = useCallback((name: string) => {
    setHiredAgents((prev) => prev.filter((a) => a.name !== name));
  }, []);

  const markHiredExecuting = useCallback(
    (subtaskId: string, name: string, skill?: string | null) => {
      if (!isSpecialist(name)) return;
      pendingHiresRef.current.set(subtaskId, name);
      const count = (activeCountRef.current.get(name) ?? 0) + 1;
      activeCountRef.current.set(name, count);
      upsertHired(name, { runStatus: "executing", skill });
    },
    [upsertHired],
  );

  const markHiredFinished = useCallback(
    (subtaskId: string, assignee: string, _failed: boolean) => {
      pendingHiresRef.current.delete(subtaskId);
      if (!isSpecialist(assignee)) return;

      const count = (activeCountRef.current.get(assignee) ?? 1) - 1;
      if (count <= 0) {
        activeCountRef.current.delete(assignee);
      } else {
        activeCountRef.current.set(assignee, count);
      }

      upsertHired(assignee, {
        runStatus: count > 0 ? "executing" : "done",
      });
    },
    [upsertHired],
  );

  const markHiredFallback = useCallback(
    (subtaskId: string) => {
      const planned = pendingHiresRef.current.get(subtaskId);
      pendingHiresRef.current.delete(subtaskId);
      if (!planned) return;

      const count = (activeCountRef.current.get(planned) ?? 1) - 1;
      if (count <= 0) {
        activeCountRef.current.delete(planned);
        removeHired(planned);
      } else {
        activeCountRef.current.set(planned, count);
        upsertHired(planned, { runStatus: "executing" });
      }
    },
    [removeHired, upsertHired],
  );

  const send = useCallback(
    async (text: string) => {
      const turnId = uid();
      let turn: OrchestrationTurn = {
        id: turnId,
        cards: [
          makeCard("user", { status: "done", content: text }),
          makeCard("planner", { status: "running", content: "" }),
        ],
      };
      setTurns((prev) => [...prev, turn]);
      setIsStreaming(true);
      setStatusMessage("Planning…");
      resetHiredAgents();

      let route: string | undefined;
      let subtasks: SubtaskItem[] = [];
      let answer = "";
      const uiItems: UiItem[] = [];

      const patchTurn = (fn: (t: OrchestrationTurn) => OrchestrationTurn) => {
        setTurns((prev) => prev.map((t) => (t.id === turnId ? fn(t) : t)));
      };

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

        const reader = res.body.getReader();
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

            if (event === "thinking" && data.delta) {
              patchTurn((t) => {
                const content = (t.cards.find((c) => c.type === "planner")?.content ?? "") + String(data.delta);
                return updateCard(t, "planner", { status: "running", content });
              });
            } else if (event === "thinking_done") {
              patchTurn((t) => updateCard(t, "planner", { status: "done" }));
            } else if (event === "plan" && data.data) {
              const plan = data.data as Record<string, unknown>;
              route = (plan.route as string) ?? route;
              const steps = (plan.steps as { title: string; detail: string }[]) ?? [];
              const rawSubtasks = (plan.subtasks as SubtaskItem[]) ?? [];
              subtasks = rawSubtasks.map((s) => ({ ...s, status: "pending" as StepStatus }));
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
              patchTurn((t) =>
                updateCard(t, "planner", {
                  status: "done",
                  content: planText || t.cards.find((c) => c.type === "planner")?.content,
                  subtasks: undefined,
                }),
              );
            } else if (event === "route_decision") {
              route = (data.route as string) ?? route;
              const complexity = data.complexity as string | undefined;
              patchTurn((t) => {
                let next = ensureCard(t, "routing");
                next = updateCard(next, "routing", {
                  status: "done",
                  route,
                  complexity,
                  content: `Route: ${route}${complexity ? `\nComplexity: ${complexity}` : ""}`,
                });
                return next;
              });
            } else if (event === "execution_start") {
              patchTurn((t) => {
                let next = ensureCard(t, "delegation");
                next = updateCard(next, "delegation", {
                  status: "running",
                  subtasks: subtasks.length
                    ? subtasks
                    : [{ id: "direct", title: "Direct execution", status: "pending" }],
                  content:
                    route === "simple"
                      ? "Simple route — thinking agent will answer directly."
                      : `Delegating ${subtasks.length || 1} subtask(s) to specialists.`,
                });
                next = ensureCard(next, "agent-exec");
                return next;
              });
            } else if (event === "subtask_start") {
              const id = data.id as string;
              const title = data.title as string;
              const assignee = data.assignee as string;
              const planned = subtasks.find((s) => s.id === id);
              const skill = planned?.skill ?? null;
              if (isSpecialist(assignee)) {
                markHiredExecuting(id, assignee, skill);
              }
              patchTurn((t) => {
                let next = ensureCard(t, "agent-exec");
                const existing = next.cards.find((c) => c.type === "agent-exec");
                const list = [...(existing?.subtasks ?? subtasks)];
                const idx = list.findIndex((s) => s.id === id);
                const item: SubtaskItem = {
                  id,
                  title,
                  assignee,
                  status: "running",
                };
                if (idx >= 0) list[idx] = { ...list[idx], ...item, status: "running" };
                else list.push(item);
                subtasks = list;
                return updateCard(next, "agent-exec", {
                  status: "running",
                  subtasks: list,
                });
              });
              if (route === "simple") {
                patchTurn((t) => {
                  let next = ensureCard(t, "delegation");
                  next = updateCard(next, "delegation", {
                    status: "done",
                    content: "Thinking agent handling request.",
                  });
                  return next;
                });
              }
            } else if (event === "subtask_done") {
              const id = data.id as string;
              const assignee = data.assignee as string;
              const st = data.status as string;
              const isFallback = assignee === "thinking";
              if (isFallback) {
                markHiredFallback(id);
              } else if (isSpecialist(assignee)) {
                markHiredFinished(id, assignee, st === "failed");
              }
              patchTurn((t) => {
                const next = ensureCard(t, "agent-exec");
                const card = next.cards.find((c) => c.type === "agent-exec");
                const list = (card?.subtasks ?? subtasks).map((s) =>
                  s.id === id
                    ? {
                        ...s,
                        status: (isFallback ? "fallback" : st === "failed" ? "fallback" : "done") as StepStatus,
                        assignee,
                      }
                    : s,
                );
                const allDone = list.every((s) => s.status === "done" || s.status === "fallback");
                return updateCard(next, "agent-exec", {
                  status: allDone ? "done" : "running",
                  subtasks: list,
                });
              });
              patchTurn((t) => updateCard(t, "delegation", { status: "done" }));
            } else if (event === "execution_done") {
              patchTurn((t) => {
                let next = updateCard(t, "delegation", { status: "done" });
                const exec = next.cards.find((c) => c.type === "agent-exec");
                if (!exec) {
                  next = ensureCard(next, "agent-exec");
                  next = updateCard(next, "agent-exec", {
                    status: route === "simple" ? "done" : "done",
                    content: route === "simple" ? "Handled by thinking agent." : undefined,
                  });
                }
                return next;
              });
            } else if (event === "answer" && data.delta) {
              answer += String(data.delta);
              patchTurn((t) => {
                let next = t;
                if (route === "simple") {
                  next = ensureCard(next, "delegation");
                  next = updateCard(next, "delegation", {
                    status: "done",
                    content: "Simple route — thinking agent answering directly.",
                  });
                  next = ensureCard(next, "agent-exec");
                  next = updateCard(next, "agent-exec", {
                    status: "running",
                    subtasks: [
                      {
                        id: "thinking",
                        title: "Direct answer",
                        assignee: "thinking",
                        status: "running",
                      },
                    ],
                  });
                }
                next = ensureCard(next, "output");
                return updateCard(next, "output", {
                  status: "running",
                  content: answer,
                  mono: false,
                });
              });
            } else if (event === "answer_done") {
              patchTurn((t) => {
                let next = ensureCard(t, "output");
                next = updateCard(next, "output", {
                  status: "done",
                  content: (data.text as string) || answer,
                });
                if (route === "simple") {
                  next = ensureCard(next, "agent-exec");
                  next = updateCard(next, "agent-exec", {
                    status: "done",
                    subtasks: [
                      {
                        id: "thinking",
                        title: "Direct answer",
                        assignee: "thinking",
                        status: "done",
                      },
                    ],
                  });
                }
                return next;
              });
            } else if (event === "ui" && data.name !== "text-card") {
              uiItems.push({ name: data.name as string, props: (data.props as Record<string, unknown>) ?? {} });
              patchTurn((t) => {
                let next = ensureCard(t, "gen-ui");
                return updateCard(next, "gen-ui", {
                  status: "running",
                  uiComponent: data.name as string,
                  uiProps: (data.props as Record<string, unknown>) ?? {},
                });
              });
            } else if (event === "gen_ui_selected") {
              const component = data.component as string | null | undefined;
              if (component) {
                const props = (data.props as Record<string, unknown>) ?? {};
                uiItems.push({ name: component, props });
                patchTurn((t) => {
                  let next = ensureCard(t, "gen-ui");
                  return updateCard(next, "gen-ui", {
                    status: "done",
                    uiComponent: component,
                    uiProps: props,
                  });
                });
              } else {
                patchTurn((t) => {
                  let next = ensureCard(t, "gen-ui");
                  return updateCard(next, "gen-ui", {
                    status: "done",
                    uiComponent: null,
                    content: String(data.reason ?? "Plain text response."),
                  });
                });
              }
            } else if (event === "status" && data.message) {
              setStatusMessage(String(data.message));
            } else if (event === "final") {
              if (data.thread_id) {
                threadIdRef.current = String(data.thread_id);
                localStorage.setItem(THREAD_KEY, threadIdRef.current);
              }
              if (!answer && data.text) answer = String(data.text);
              const finalUi = (data.ui as UiItem[]) ?? [];
              for (const item of finalUi) {
                if (item.name !== "text-card") uiItems.push(item);
              }
              patchTurn((t) => {
                let next = t;
                if (answer) {
                  next = ensureCard(next, "output");
                  next = updateCard(next, "output", { status: "done", content: answer });
                }
                next = ensureCard(next, "gen-ui");
                const lastUi = uiItems[uiItems.length - 1];
                return updateCard(next, "gen-ui", {
                  status: lastUi ? "done" : "done",
                  uiComponent: lastUi?.name ?? null,
                  uiProps: lastUi?.props ?? {},
                  content: lastUi ? undefined : "No rich UI component selected.",
                });
              });
            } else if (event === "done") {
              if (data.thread_id) {
                threadIdRef.current = String(data.thread_id);
                localStorage.setItem(THREAD_KEY, threadIdRef.current);
              }
            } else if (event === "error") {
              patchTurn((t) => ({
                ...t,
                cards: [
                  ...t.cards,
                  makeCard("output", {
                    status: "fallback",
                    content: String(data.message ?? "Request failed"),
                    mono: true,
                  }),
                ],
              }));
            }
          }
        }

        // Simple route may skip execution events — ensure cards exist
        patchTurn((t) => {
          let next = t;
          if (!next.cards.some((c) => c.type === "routing") && route) {
            next = ensureCard(next, "routing");
            next = updateCard(next, "routing", { status: "done", route });
          }
          if (route === "simple" && !next.cards.some((c) => c.type === "delegation")) {
            next = ensureCard(next, "delegation");
            next = updateCard(next, "delegation", {
              status: "done",
              content: "Simple route — no specialist delegation.",
            });
          }
          if (answer && !next.cards.some((c) => c.type === "output")) {
            next = ensureCard(next, "output");
            next = updateCard(next, "output", { status: "done", content: answer });
          }
          if (!next.cards.some((c) => c.type === "gen-ui")) {
            next = ensureCard(next, "gen-ui");
            const lastUi = uiItems[uiItems.length - 1];
            next = updateCard(next, "gen-ui", {
              status: "done",
              uiComponent: lastUi?.name ?? null,
              uiProps: lastUi?.props ?? {},
              content: lastUi ? undefined : "Plain text response.",
            });
          }
          return next;
        });
      } catch (err) {
        patchTurn((t) => ({
          ...t,
          cards: [
            ...t.cards,
            makeCard("output", {
              status: "fallback",
              content: err instanceof Error ? err.message : String(err),
              mono: true,
            }),
          ],
        }));
      } finally {
        setIsStreaming(false);
        setStatusMessage(null);
      }
    },
    [markHiredExecuting, markHiredFallback, markHiredFinished, resetHiredAgents],
  );

  return { turns, send, isStreaming, statusMessage, hiredAgents };
}

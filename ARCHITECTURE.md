# Cognilance architecture

## Packages

| Path | Role |
|------|------|
| `cognilance/` | Python SDK (`CognilanceManager` / `CognilanceWorker`, A2A) |
| `registry/` | Marketplace catalog API (Docker, `:8088`) |
| `orchestrator/` | LangGraph supervisor + FastAPI chat + OAuth + tool-proxy |
| `agents/` | Marketplace workers (one folder per skill) |
| `agent-host/` | Local ZIP upload / run portal |
| `web/` | Marketing site |

## Chat wire contract (SSE)

Event names the chat UI depends on (keep stable):

| Event | Meaning |
|-------|---------|
| `session_created` | Mission/session ids |
| `catalog` | Online marketplace agents |
| `thinking` / `thinking_done` | Planner reasoning stream |
| `plan` | Plan + `subtasks` |
| `route_decision` | `simple` vs `complex` |
| `subtask_start` / `subtask_done` | Hire/app execution |
| `answer` / `answer_done` | Final text stream |
| `final` | Aggregated result (+ optional `document_id`) |
| `done` | Stream complete |
| `error` / `session_aborted` | Failure / cancel |

## Router-first planning

```
query → DeterministicRouter
         ├─ hit  → emit synthetic plan; skip planner LLMs; execute
         └─ miss → one LLM plan call → execute
```

**Policy:** If the catalog has a matching skill and the required integration is connected → `hire:<skill>`. Else if the integration is connected → `app:*`. Else → `thinking` + connect CTA.

## Hire + tool-proxy

1. Orchestrator discovers online agents from the registry.
2. On `hire:<skill>`, issues a short-lived HMAC grant scoped to that skill.
3. Agent `proxy.py` calls back to `/tools/gmail/*` or `/tools/docs/*`.
4. Orchestrator runs Google APIs with the end-user OAuth token.

Agents never hold OAuth secrets.

## Memory

- **ConversationStore** is the source of truth for chat history (`conversation_id`).
- Missions/sessions are keyed by `conversation_id` and scoped to `user_id`.
- Chat runs do not rely on LangGraph checkpoint resume across turns.

## Runtime SSE

Live `/chat/stream` pushes events through an in-process event bus (persist + publish). Reconnect/replay uses `GET /missions/{id}/events?after=`.

## Demo

```bash
COGNILANCE_DEMO=1 ./scripts/start_demo.sh
```

Sets demo-safe secret defaults. Production must set distinct `ORCHESTRATOR_SESSION_SECRET` and `TOOL_PROXY_SIGNING_KEY`.

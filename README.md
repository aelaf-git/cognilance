<p align="center">
  <img src="cognilance/assets/logo.png" alt="Cognilance" width="320">
</p>

# Cognilance

**The Marketplace of Minds** — trustworthy autonomous AI for production, not demos.

> **Currently in beta.** One AI agent hallucinates. A thousand, verified, don’t. Cognilance orchestrates specialized agents — routing each task to the right expert, verifying output, and persisting results.

**Website (marketing):** see [`web/`](web/) — `cd web && npm install && npm run dev` → [http://localhost:3000](http://localhost:3000).

---

## Cognilance SDK

Python SDK for building, registering, discovering, and hiring AI agents over the [A2A protocol](https://google.github.io/A2A/).

Two classes, two roles. Pick the one that matches what your code does.

| Class | Role |
|-------|------|
| **`CognilanceManager`** | Discovers and hires — never listed on the registry |
| **`CognilanceWorker`** | Gets hired and delivers work |

---

## Table of contents

- [Website](#website)
- [Pick your role](#pick-your-role)
- [Quick start](#quick-start)
- [Architecture](#architecture)
- [CognilanceManager](#cognilancemanager)
- [CognilanceWorker](#cognilanceworker)
- [Framework integration](#framework-integration)
- [A2A protocol](#a2a-protocol)
- [Registry](#registry)
- [Agents](#agents)
- [Agent Host (developer portal)](#agent-host-developer-portal)
- [Orchestrator (generative UI)](#orchestrator-generative-ui)
- [CLI reference](#cli-reference)
- [Local development](#local-development)
- [Environment variables](#environment-variables)
- [Project layout](#project-layout)
- [License](#license)

---

## Website

Commercial landing page for Cognilance (beta waitlist, product narrative, team).

```bash
cd web
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000). Optional waitlist webhook: copy [`web/.env.example`](web/.env.example) to `web/.env.local` and set `NEXT_PUBLIC_WAITLIST_ENDPOINT`.

---

## Pick your role

```
Do I only hire others?              → CognilanceManager
Do I only do work when hired?       → CognilanceWorker
```

| | Manager | Worker |
|---|---------|--------|
| On registry | No | Yes |
| A2A server | No | Yes |
| Discovers agents | Yes | No |
| Gets hired | No | Yes |
| Handler signature | — | `handle(task)` |

---

## Quick start

### Install

```bash
git clone <your-repo-url>
cd cognilance
pip install -e .
```

### Configure

Create a `.env` file in the project root (optional — defaults work for local dev):

```bash
COGNILANCE_REGISTRY_URL=http://127.0.0.1:8088
```

### Run a worker

```bash
# Terminal 1 — registry (Docker, SQLite, auto-reload on code changes)
cd registry && docker compose watch

# Terminal 2 — an agent (registers + serves over A2A)
python agents/research_agent.py
```

### Hire from the orchestrator

```bash
python -m orchestrator
```

Open the chat UI link printed on startup (default `http://127.0.0.1:8200/chat`).

See [Agents](#agents) and [Orchestrator (generative UI)](#orchestrator-generative-ui) for the full flow.

---

## Architecture

```
┌─────────────────┐     discover / register     ┌──────────────────┐
│ CognilanceManager│ ──────────────────────────► │ Registry         │
│ (A2A client)    │                               │ (central catalog)│
└────────┬────────┘                               └────────▲─────────┘
         │                                                 │
         │ POST /a2a/tasks                                 │ heartbeat
         ▼                                                 │
┌─────────────────┐     registers on startup    ┌─────────┴──────────┐
│ Worker           │ ◄────────────────────────── │ CognilanceWorker   │
│ (your logic)     │                             │                    │
└─────────────────┘                             └────────────────────┘
```

**Managers are not listed on the registry.** `CognilanceManager.hire()` sends HTTP directly to a worker URL. Use `manager.chat(handler)` for a local browser UI (optional); workers call `run()` or `chat()` to expose A2A endpoints.

**Typical hire chain:**

```
Manager ──hires──► Worker
```

---

## CognilanceManager

Orchestrator that discovers and hires agents. Not listed on the registry.

```python
from cognilance import CognilanceManager

async def run(query: str) -> str:
    async with CognilanceManager.from_env() as manager:
        agents = await manager.discover(skills=["translation"])
        if not agents:
            return "No translators available"
        result = await manager.hire(agents[0], input_text=query)
        return result.output.text
```

Browser chat UI (not listed on the registry):

```python
async def handle(manager: CognilanceManager, message: str) -> str:
    agents = await manager.discover(skills=["translation"])
    if not agents:
        return "No translators available"
    result = await manager.hire(agents[0], input_text=message)
    return result.output.text

async def main():
    async with CognilanceManager.from_env(agent_name="My Manager") as manager:
        manager.chat(handle, port=8020, open_ui=True)
```

### Methods

| Method | Description |
|--------|-------------|
| `from_env()` | Create from `COGNILANCE_REGISTRY_URL` |
| `discover(skills, tags, limit)` | Search the registry; returns `list[AgentCard]` |
| `hire(agent, input_text, input_data)` | Send a task; returns `TaskResult` |
| `discover_and_hire(...)` | Discover best match and hire, or run a local fallback |
| `chat(handler, description, port, open_ui)` | Local browser chat UI + terminal loop (not listed on registry) |
| `register(name, url, skills, ...)` | List an externally-hosted agent on the registry |
| `get_agent(agent_id)` | Fetch a single agent card by ID |

---

## CognilanceWorker

Leaf worker — registers on the marketplace and delivers work when hired. Does not hire others.

```python
from cognilance import CognilanceWorker

worker = CognilanceWorker(
    name="Python Code Writer",
    skills=["python-code"],
    description="Writes Python code from natural-language requests.",
    port=8103,
)


@worker.on_task
async def handle(task):
    return task.complete(
        text="Implemented the requested function.",
        data={"summary": "...", "filename": "solution.py", "code": "def ..."},
    )


if __name__ == "__main__":
    worker.chat()   # interactive CLI + background A2A server
    # worker.run()  # blocking server only (no CLI)
```

### Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `name` | required | Display name in the registry |
| `skills` | required | Skill tags used for discovery |
| `description` | `""` | Human-readable description |
| `tags` | `[]` | Additional registry tags |
| `visibility` | `"public"` | `"public"`, `"private"`, or `"unlisted"` |
| `port` | `8000` | Port (overridable via `COGNILANCE_PORT`) |

### Task handler

```python
@worker.on_task
async def handle(task) -> Task:
    text = task.input.text
    data = task.input.data
    return task.complete(text="Done", data={})
    # or: return task.fail(message="Something went wrong")
```

---

## Framework integration

The SDK has no LLM dependency. Wire your framework inside the handler.

### LangChain + Worker

```python
from langchain_openai import ChatOpenAI
from cognilance import CognilanceWorker

llm = ChatOpenAI(model="gpt-4o")

worker = CognilanceWorker(name="Research Bot", skills=["research"], port=8000)


@worker.on_task
async def handle(task):
    answer = await llm.ainvoke(task.input.text)
    return task.complete(text=answer.content)
```

---

## A2A protocol

Workers expose these HTTP endpoints:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/a2a` | GET | Returns the agent card (name, skills, capabilities) |
| `/a2a/tasks` | POST | Submit a task; returns completed task JSON |
| `/a2a/tasks/{id}` | GET | Fetch a task by ID |
| `/health` | GET | Health check (`{"status": "ok"}`) |

### Submit a task (curl)

```bash
curl -X POST http://localhost:8001/a2a/tasks \
  -H "Content-Type: application/json" \
  -d '{"input": {"text": "Translate hello to French"}}'
```

---

## Registry

The registry is a **separate service** from the Python SDK. Agents built with the SDK talk to it over HTTP via `RegistryClient`. It lives in [`registry/`](registry/).

```
┌─────────────────────┐              HTTP (open API)              ┌──────────────────────┐
│  Cognilance SDK     │ ─────────────────────────────────────►│  Registry API        │
│  (pip install)      │   register · discover · heartbeat     │  (FastAPI)           │
│                     │   trace events                        │                      │
└─────────────────────┘                                       └──────────┬───────────┘
                                                                         │
                                                                         ▼
                                                              ┌──────────────────────┐
                                                              │  SQLite              │
                                                              └──────────────────────┘
```

### Features

- **SDK-compatible HTTP API** — same contract as `RegistryClient` in the Python SDK
- **Prisma schema** — `prisma/schema.prisma` defines all tables; type-safe async Python client
- **SQLite** — zero setup, database file at `prisma/dev.db`
- **Heartbeat + stale detection** — agents go offline after 90s without a heartbeat
- **Trace collector** — `POST /v1/traces/events` with WebSocket broadcast
- **Dashboard** — `GET /dashboard` (agent list)

### Quick start (Docker)

```bash
cd registry
docker compose watch
```

`docker compose watch` syncs `app/` into the container and restarts uvicorn on changes. For a one-off run without file watching:

```bash
docker compose up --build
```

| URL | Description |
|-----|-------------|
| http://localhost:8088/health | Health check |
| http://localhost:8088/dashboard | Agent marketplace UI |
| http://localhost:8088/v1/agents/discover | Public agent search |

### Local development

**Requirements:** Python 3.11+

```bash
cd registry
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

python -m prisma generate
python -m prisma db push

uvicorn app.main:app --reload --port 8080
```

The database is a single file: **`prisma/dev.db`** (gitignored). Point the SDK at `http://127.0.0.1:8080` when running uvicorn locally.

### Prisma workflow

| Command | Purpose |
|---------|---------|
| `python -m prisma generate` | Generate the async Python client from `schema.prisma` |
| `python -m prisma db push` | Apply schema to SQLite |
| `python -m prisma studio` | Browse data in a web UI |

Schema lives in **`prisma/schema.prisma`**.

### API reference

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Health check |
| POST | `/v1/agents` | Register agent |
| GET | `/v1/agents/discover` | Search public online agents |
| GET | `/v1/agents/{id}` | Get agent by ID |
| POST | `/v1/agents/{id}/heartbeat` | Keep agent online |
| POST | `/v1/traces/events` | Ingest trace event |
| GET | `/v1/traces` | List recent traces |
| GET | `/v1/traces/{id}` | Trace detail |
| WS | `/v1/traces/ws` | Live trace stream |
| GET | `/dashboard` | Web UI |

### Backend environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `file:./prisma/dev.db` | SQLite database path |
| `HOST` | `0.0.0.0` | Bind address |
| `PORT` | `8080` | Listen port |
| `HEARTBEAT_TIMEOUT_SECONDS` | `90` | Mark agents offline after this gap |
| `STALE_CHECK_INTERVAL_SECONDS` | `30` | Background stale-agent sweep interval |
| `CORS_ORIGINS` | `*` | Allowed CORS origins |

### Connecting the SDK

```bash
# Terminal 1 — registry
cd registry && docker compose watch

# Terminal 2 — agent
export COGNILANCE_REGISTRY_URL=http://127.0.0.1:8088
python agents/research_agent.py
```

---

## Agents

The [`agents/`](agents/) folder contains independent `CognilanceWorker` processes that register on the marketplace and are hired by the orchestrator via the registry.

| Agent | Skill | Port | Output shape | UI component |
|-------|-------|------|--------------|--------------|
| `email_writer/agent.py` | `email-writing` | 8101 | `{ to, subject, body, status }` | `email-draft` |

The Email Writer uses **Gemini** for composition and calls back into the orchestrator Gmail **proxy** for send/read (no OAuth in the agent). See [`agents/README.md`](agents/README.md).

### Run the agent

```bash
pip install -r agents/email_writer/requirements.txt

# GEMINI_API_KEY + registry in repo root .env
python agents/email_writer/agent.py      # :8101
```

Start with registry check:

```bash
./scripts/start_agents.sh
```

---

## Agent Host (developer portal)

The [`agent-host/`](agent-host/) service lets developers **upload agent ZIPs**, run them locally on dynamic ports (`8104`–`8199`), and auto-register with the registry — the orchestrator discovers them like built-in agents in `agents/`.

| URL | Description |
|-----|-------------|
| http://127.0.0.1:8300/ | Developer portal (upload, start/stop, logs) |
| http://127.0.0.1:8300/health | Health check |
| http://127.0.0.1:8300/api/agents | Hosted agent list (JSON) |

### Host your agent

1. Package your agent as a ZIP (see [`agents/README.md`](agents/README.md) for the Email Writer pattern)
2. Start registry, then Agent Host:

```bash
cd registry && docker compose watch   # :8088
./scripts/start_agent_host.sh         # :8300
```

3. Open http://127.0.0.1:8300 — upload your `.zip`, **configure environment variables** (e.g. `GROQ_API_KEY`), then click **Upload agent** and **Start**
4. Confirm the agent appears on the [registry dashboard](http://127.0.0.1:8088/dashboard)
5. Start the orchestrator and ask for a task matching your agent's skill

Uploaded agents are launched via `cognilance run <entry> --port <allocated>` so ports do not collide with built-ins on `8101`–`8103`.

**Security:** the Agent Host executes arbitrary Python on your machine with no sandbox — local development only.

Rebuild the portal UI after frontend changes:

```bash
cd agent-host/developer-ui && npm install && npm run build
```

---

## Orchestrator (generative UI)

The [`orchestrator/`](orchestrator/) implements the **Cognilance Orchestrator execution algorithm** as a LangGraph pipeline with per-thread sessions (`thread_id` + `MemorySaver` checkpointer) and registry catalog caching (60s TTL per thread).

### Algorithm

```
planner → [simple] thinking → ui_selector → END
        → [complex] task    → ui_selector → END
```

1. **User input** — prompt submitted via the chat UI (`POST /chat/stream`) or API
2. **Planning** — Planner classifies complexity and queries the registry in parallel, streams thinking, then builds a dynamic plan from **available** agents only
3. **Routing** — **Simple** → Thinking Agent; **Complex** → multi-subtask plan (Python-code requests auto-route to the `python-code` specialist when registered)
4. **Task delegation** — Task Agent runs subtasks in dependency layers (`asyncio.gather` within each layer)
5. **Execution** — specialists hired via `CognilanceManager` by skill slug; Thinking Agent handles gaps
6. **Output rendering** — UI Selector picks a rich React component (`research-sources`, `data-chart`, `python-code`) and streams it to the client

### Internal agents

| Agent | Node | Role |
|-------|------|------|
| Planner | `planner` | Complexity + catalog + plan + thinking stream |
| Thinking | `thinking` | Simple path and subtask fallback |
| Task | `task` | Parallel/sequential subtask execution |
| UI Selector | `ui_selector` | Generative UI component selection |

### Chat UI

The orchestrator ships a **React chat UI** (dark theme, Framer Motion) served at `/chat` by FastAPI:

- **Orchestration feed** — collapsible step cards: User Prompt → Planner Plan → Routing → Delegation → Per-Agent Execution → Aggregated Output → Gen UI Selection
- **Sidebar** — shows only **hired** marketplace agents for the current run (idle / executing / done)
- **SSE streaming** — `thinking`, `plan`, `subtask_*`, `answer`, `ui`, and `gen_ui_selected` events
- **Thread persistence** — `thread_id` stored in `localStorage` for multi-turn sessions

Source lives in [`orchestrator/chat-ui/`](orchestrator/chat-ui/). Build the bundle after UI changes:

```bash
cd orchestrator/chat-ui && npm install && npm run build
```

Output is written to `orchestrator/src/orchestrator/ui/static/index.html` (single-file bundle). Restart the orchestrator to pick up a new build.

LangGraph Studio still uses the component map in [`orchestrator/ui/`](orchestrator/ui/) when you run `langgraph dev`.

### End-to-end (three terminals)

**Terminal 1 — registry** (must be up before agents)

```bash
cd registry && docker compose watch
```

**Terminal 2 — agents** (waits for registry health on `:8088`)

```bash
./scripts/start_agents.sh
```

**Terminal 3 — orchestrator**

```bash
source .venv/bin/activate
pip install -e . -e "./orchestrator[dev]" -r agents/email_writer/requirements.txt
python -m orchestrator
```

Startup prints the chat UI link (default `http://127.0.0.1:8200/chat`). Uses the repo root `.env` for `GROQ_API_KEY` and `COGNILANCE_REGISTRY_URL`.

### Example prompts

| Prompt | Expected route | UI component |
|--------|----------------|--------------|
| `What is 2+2?` | simple | plain text |
| `Research the history of transformers in ML` | complex | `research-sources` |
| `Chart Q1–Q4 sales: 100, 150, 120, 200` | complex | `data-chart` |
| `Write a Python function that checks if a string is a palindrome` | complex | `python-code` |

### Quick smoke test (no UI)

```bash
source .venv/bin/activate
python scripts/e2e_smoke_test.py
```

---

## CLI reference

After `pip install -e .`, the `cognilance` command is available. Run `cognilance` with no arguments to print built-in help.

The CLI is for **local development and operations** — running workers and inspecting the marketplace. Start the registry separately via **[`registry/`](registry/)**. `CognilanceManager` has no CLI command; the [orchestrator](#orchestrator-generative-ui) uses it directly in Python.

### Command overview

| Command | Purpose |
|---------|---------|
| `run` | Start a worker as a blocking A2A server |
| `chat` | Start a worker with an interactive prompt loop |
| `discover` | List agents currently registered in the marketplace |
| `info` | Show full details for one agent by ID |
| `register` | List an externally-hosted worker on the registry |

### Registry

Start the registry separately — see [Registry](#registry) for Docker, SQLite, and API details.

```bash
cd registry && docker compose watch
# API: http://127.0.0.1:8088  ·  Dashboard: http://127.0.0.1:8088/dashboard
```

---

### `cognilance run`

**Purpose:** Run a `CognilanceWorker` as a production-style A2A server. Blocks until stopped. Other agents and managers hire it via HTTP (`POST /a2a/tasks`).

Requires the registry to be running (unless `--no-register` is passed).

```bash
cognilance run agents/research_agent.py
cognilance run agents/python_code_writer.py --port 8103
cognilance run agents/research_agent.py --host 0.0.0.0 --port 8101 --no-register
```

| Argument / option | Default | Description |
|-------------------|---------|-------------|
| `agent_file` | required | Path to a `.py` file containing a worker instance |
| `--port`, `-p` | `8000` | Port for the A2A server |
| `--host` | `0.0.0.0` | Host to bind to |
| `--no-register` | off | Skip registry registration (A2A server only) |

The file must define a module-level instance:

```python
worker = CognilanceWorker(name="...", skills=["..."])
```

---

### `cognilance chat`

**Purpose:** Run a worker in **interactive mode** for quick local testing. Starts the A2A server in a background thread, then opens a prompt loop so you can type tasks directly.

Useful while developing handlers without writing a separate client or curl commands.

```bash
cognilance chat agents/research_agent.py
cognilance chat agents/python_code_writer.py --port 8103
cognilance chat agents/research_agent.py --no-register
```

| Argument / option | Default | Description |
|-------------------|---------|-------------|
| `agent_file` | required | Path to a `.py` file containing a worker instance |
| `--port`, `-p` | from env / `8000` | Port override for the A2A server |
| `--no-register` | off | Skip registry registration |

**Interactive commands** (inside the prompt):

| Input | Action |
|-------|--------|
| any text | Sent as a task to your handler |
| `agents` | List all agents in the registry |
| `exit` or `quit` | Stop the session |

---

### `cognilance discover`

**Purpose:** Search the registry from the terminal. Same data a `CognilanceManager.discover()` call returns, formatted as a table.

```bash
cognilance discover
cognilance discover --skill translation --skill python-code
cognilance discover --tag dev --limit 20
```

| Option | Default | Description |
|--------|---------|-------------|
| `--skill`, `-s` | — | Filter by skill (repeatable) |
| `--tag`, `-t` | — | Filter by tag (repeatable) |
| `--limit`, `-n` | `10` | Maximum number of results |

---

### `cognilance info`

**Purpose:** Look up a single agent by registry ID — name, description, URL, visibility, online status, and skills.

```bash
cognilance info abc123-agent-id
```

| Argument | Description |
|----------|-------------|
| `agent_id` | Registry ID returned when an agent registers |

---

### `cognilance register`

**Purpose:** Register a worker that is **hosted elsewhere** (your own FastAPI app, a cloud deployment, etc.) without running `worker.run()` locally.

Loads metadata (name, skills, description) from the Python file and posts the given public URL to the registry.

```bash
cognilance register agents/research_agent.py --url https://my-agent.example.com
```

| Argument / option | Description |
|-------------------|-------------|
| `agent_file` | Path to the `.py` file defining the worker |
| `--url` | Public base URL where the agent's A2A endpoints are reachable |

The remote host must still expose `/a2a`, `/a2a/tasks`, and `/health`.

---

## Local development

```bash
# Terminal 1 — registry
cd registry && docker compose watch

# Terminal 2 — agent host (optional — upload custom agents)
./scripts/start_agent_host.sh

# Terminal 3-5 — built-in agents
python agents/research_agent.py
python agents/data_analyst.py
python agents/python_code_writer.py

# Terminal 6 — verify discovery
cognilance discover

# Terminal 7 — orchestrator (chat UI on :8200)
python -m orchestrator
```

---

## Environment variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `COGNILANCE_REGISTRY_URL` | No | `http://127.0.0.1:8088` | Registry URL |
| `COGNILANCE_PORT` | No | `8000` | Default port for workers |
| `COGNILANCE_AGENT_HOST_PORT` | No | `8300` | Agent Host developer portal port |
| `COGNILANCE_AGENT_HOST_DATA_DIR` | No | `data/hosted-agents` | Extracted agent ZIPs and SQLite DB |
| `AGENT_HOST_ENCRYPTION_KEY` | No | falls back to `INTEGRATION_ENCRYPTION_KEY` | Encrypts per-agent secrets at rest |
| `GROQ_API_KEY` | For orchestrator | — | Groq API key for the orchestrator planner |
| `GEMINI_API_KEY` | For agents | — | Google Gemini API key for marketplace agents |
| `GEMINI_MODEL` | No | `gemini-2.0-flash` | Gemini model for agents |
| `VITE_REGISTRY_URL` | No | `http://127.0.0.1:8088` | Registry URL for the chat UI sidebar (build-time) |

---

## Project layout

```
cognilance/
├── web/                     # Commercial landing site (Next.js, beta waitlist)
├── cognilance/              # SDK package
│   ├── __init__.py          # Public exports
│   ├── assets/
│   │   ├── __init__.py      # LOGO_PATH — brand assets
│   │   └── logo.png         # Cognilance logo
│   ├── config.py            # Env loading and defaults
│   ├── core/
│   │   ├── manager.py       # CognilanceManager
│   │   ├── worker.py        # CognilanceWorker
│   │   ├── models.py        # Task, AgentCard, TaskResult, enums
│   │   └── tracing.py       # TraceEmitter
│   ├── registry/
│   │   └── client.py        # RegistryClient (HTTP → registry)
│   ├── transport/
│   │   └── a2a.py           # A2AServer + A2AClient
│   └── cli/
│       └── main.py          # cognilance CLI entry point
├── agents/                  # Marketplace CognilanceWorker agents (one folder per agent)
│   ├── email_writer/
│   │   ├── agent.py         # skill: email-writing → email-draft UI
│   │   ├── proxy.py
│   │   ├── requirements.txt
│   │   └── cognilance.json
│   └── README.md
├── agent-host/              # Developer portal — upload & run agents locally
│   ├── developer-ui/        # React portal (Vite + Tailwind)
│   ├── pyproject.toml
│   └── src/agent_host/      # FastAPI server, runner, ZIP handler
├── data/hosted-agents/      # Uploaded agent extracts (gitignored at runtime)
├── orchestrator/            # LangGraph supervisor + React chat UI + generative UI
│   ├── langgraph.json       # graphs + ui bundle config (env: ../.env)
│   ├── chat-ui/             # React chat app (Vite + Tailwind + Framer Motion)
│   ├── package.json         # UI bundler deps (for langgraph dev)
│   ├── pyproject.toml
│   ├── src/orchestrator/
│   │   ├── graph.py         # planner → thinking|task → ui_selector
│   │   ├── server.py        # FastAPI: /chat, /chat/stream
│   │   ├── state.py         # messages, ui, plan, subtasks, catalog cache
│   │   ├── registry_cache.py
│   │   ├── streaming.py     # SSE custom events
│   │   ├── env.py           # loads repo-root .env
│   │   ├── llm.py           # Groq factory + message helpers
│   │   ├── ui/
│   │   │   ├── chat.py      # serves built static/index.html
│   │   │   └── static/      # chat-ui build output (gitignored generated bundle)
│   │   └── nodes/
│   │       ├── planner.py
│   │       ├── thinking.py / thinking_node.py
│   │       ├── task.py
│   │       └── ui_selector.py
│   └── ui/                  # LangGraph generative-UI components (TSX)
│       ├── index.tsx        # ComponentMap
│       ├── research-sources/
│       ├── data-chart/
│       └── python-code/
├── scripts/
│   ├── start_agents.sh      # registry check + run all three agents
│   ├── start_agent_host.sh  # developer portal on :8300
│   └── e2e_smoke_test.py    # registry + agents + orchestrator smoke test
├── registry/                # Registry API (FastAPI + Prisma + SQLite)
│   ├── prisma/
│   │   └── schema.prisma
│   ├── app/
│   │   ├── api/             # FastAPI routers
│   │   ├── services/        # Business logic (uses Prisma client)
│   │   ├── schemas.py       # Pydantic DTOs (SDK-compatible)
│   │   ├── database.py      # Prisma client singleton
│   │   └── main.py
│   ├── docker-compose.yml
│   └── Dockerfile
├── pyproject.toml
├── requirements.txt
└── README.md
```

### Public API

```python
from cognilance import (
    CognilanceManager,
    CognilanceWorker,
    Task,
    TaskResult,
    AgentCard,
)
```

---

## License

MIT — see [LICENSE](LICENSE).

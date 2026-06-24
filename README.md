<p align="center">
  <img src="cognilance/assets/logo.png" alt="Cognilance" width="320">
</p>

# Cognilance SDK

**The Marketplace of Minds** — a Python SDK for building, registering, discovering, and hiring AI agents over the [A2A protocol](https://google.github.io/A2A/).

Three classes, three roles. Pick the one that matches what your code does.

| Class | Role |
|-------|------|
| **`CognilanceManager`** | Discovers and hires — never listed on the registry |
| **`CognilanceWorker`** | Gets hired and delivers work — leaf node, no hiring |
| **`CognilanceDelegator`** | Gets hired *and* discovers/hires others — coordinator |

---

## Table of contents

- [Pick your role](#pick-your-role)
- [Quick start](#quick-start)
- [Architecture](#architecture)
- [CognilanceManager](#cognilancemanager)
- [CognilanceWorker](#cognilanceworker)
- [CognilanceDelegator](#cognilancedelegator)
- [Framework integration](#framework-integration)
- [A2A protocol](#a2a-protocol)
- [Registry](#registry)
- [Agents](#agents)
- [Orchestrator (generative UI)](#orchestrator-generative-ui)
- [CLI reference](#cli-reference)
- [Local development](#local-development)
- [Environment variables](#environment-variables)
- [Project layout](#project-layout)
- [License](#license)

---

## Pick your role

```
Do I only hire others?              → CognilanceManager
Do I only do work when hired?       → CognilanceWorker
Do I get hired AND hire others?     → CognilanceDelegator
```

| | Manager | Worker | Delegator |
|---|---------|--------|-----------|
| On registry | No | Yes | Yes |
| A2A server | No | Yes | Yes |
| Discovers agents | Yes | No | Yes |
| Gets hired | No | Yes | Yes |
| Handler signature | — | `handle(task)` | `handle(task, manager)` |

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
│ Worker/Delegator │ ◄────────────────────────── │ CognilanceWorker   │
│ (your logic)     │                             │ CognilanceDelegator│
└─────────────────┘                             └────────────────────┘
```

**Managers are not listed on the registry.** `CognilanceManager.hire()` sends HTTP directly to a worker or delegator URL. Use `manager.chat(handler)` for a local browser UI (optional); workers and delegators call `run()` or `chat()` to expose A2A endpoints.

**Typical hire chains:**

```
Manager ──hires──► Delegator ──hires──► Worker
Manager ──hires──► Worker (direct)
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
| `hire(agent, input_text, input_data)` | Send a task to an agent; returns `TaskResult` |
| `discover_and_hire(skills, input_text, fallback_fn)` | Discover best match and hire, or run a local fallback |
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
    description="Reviews code for bugs and style.",
    port=8003,
)


@worker.on_task
async def handle(task):
    return task.complete(text=f"Reviewed: {task.input.text}")


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

## CognilanceDelegator

Coordinator — gets hired and can discover/hire other agents. Handler receives a `CognilanceManager` as its second argument (also aliased as `TaskContext`).

```python
from cognilance import CognilanceDelegator

delegator = CognilanceDelegator(
    name="Task Router",
    skills=["routing", "general"],
    port=8002,
)


@delegator.on_task
async def handle(task, manager):
    helpers = await manager.discover(skills=["summarization"])
    if helpers:
        result = await manager.hire(helpers[0], input_text=task.input.text)
        return task.complete(text=result.output.text, data={"hired": helpers[0].name})
    return task.complete(text=task.input.text)


if __name__ == "__main__":
    delegator.chat()
```

### When to use Worker vs Delegator

- **Worker** — your agent does all the work itself (translate, summarize, review code).
- **Delegator** — your agent receives a task and subcontracts parts of it to specialists on the marketplace.

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

### LangChain + Delegator

```python
from langchain_openai import ChatOpenAI
from cognilance import CognilanceDelegator, CognilanceManager

llm = ChatOpenAI(model="gpt-4o")

delegator = CognilanceDelegator(name="Research Lead", skills=["research"], port=8000)


@delegator.on_task
async def handle(task, manager: CognilanceManager):
    draft = await llm.ainvoke(task.input.text)

    editors = await manager.discover(skills=["editing"])
    if editors:
        result = await manager.hire(editors[0], input_text=draft.content)
        return task.complete(text=result.output.text)

    return task.complete(text=draft.content)
```

---

## A2A protocol

Workers and delegators expose these HTTP endpoints:

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
- **Dashboard** — `GET /dashboard` (Workers / Delegators tabs)

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

Reusable Python agents live in [`agents/`](agents/). Each one is a `CognilanceWorker` backed by [Groq](https://groq.com), registers itself on the registry on startup, and returns **structured `output.data`** that the orchestrator renders as generative UI.

| Agent | Skill | Port | Output shape | UI component |
|-------|-------|------|--------------|--------------|
| `research_agent.py` | `research` | 8101 | `{ summary, sources[] }` | `research-sources` |
| `data_analyst.py` | `data-analysis` | 8102 | `{ title, chartType, series[] }` | `data-chart` |
| `python_code_writer.py` | `python-code` | 8103 | `{ summary, filename, code }` | `python-code` |

### Run the agents

```bash
pip install -r agents/requirements.txt

# Groq + registry settings live in the repo root .env
python agents/research_agent.py      # :8101
python agents/data_analyst.py        # :8102  (separate terminal)
python agents/python_code_writer.py   # :8103  (separate terminal)
```

Each agent reads `GROQ_API_KEY` and `COGNILANCE_REGISTRY_URL` from the **repo root** `.env` (default registry `http://127.0.0.1:8088`).

Start all three at once:

```bash
./scripts/start_agents.sh
```

---

## Orchestrator (generative UI)

The [`orchestrator/`](orchestrator/) implements the **Cognilance Orchestrator execution algorithm** as a LangGraph pipeline with per-thread sessions (`thread_id` + checkpointer) and registry catalog caching.

### Algorithm

1. **User input** — prompt submitted via chat UI or API
2. **Planning** — Planner classifies complexity and queries the registry (cached per thread, 60s TTL) in parallel, then builds a dynamic plan from **available** agents only
3. **Routing** — **Simple** → Thinking Agent; **Complex** → multi-subtask plan with Thinking Agent fallback when no specialist matches
4. **Task delegation** — Task Agent runs subtasks in dependency layers (parallel within a layer)
5. **Execution** — hired agents via `CognilanceManager`; Thinking Agent handles gaps
6. **Output rendering** — UI Selector picks a rich React component (`research-sources`, `data-chart`, `python-code`)

### Internal agents

| Agent | Node | Role |
|-------|------|------|
| Planner | `planner` | Complexity + catalog + plan |
| Thinking | `thinking` | Simple path and subtask fallback |
| Task | `task` | Parallel/sequential subtask execution |
| UI Selector | `ui_selector` | Generative UI component selection |

The orchestrator ships its own **embedded chat UI** (registry-style dark theme) served by FastAPI. The client persists `thread_id` in `localStorage` for multi-turn sessions.

### End-to-end (three terminals)

**Terminal 1 — registry**

```bash
cd registry && docker compose watch
```

**Terminal 2 — agents**

```bash
./scripts/start_agents.sh
```

**Terminal 3 — orchestrator**

```bash
source .venv/bin/activate
pip install -e . -e "./orchestrator[dev]" -r agents/requirements.txt
python -m orchestrator
```

Startup prints the chat UI link (default `http://127.0.0.1:8200/chat`). Uses the repo root `.env` for `GROQ_API_KEY` and `COGNILANCE_REGISTRY_URL`.

Optional: `langgraph dev` in `orchestrator/` still works for LangGraph Studio development with the React component map in `orchestrator/ui/`.

### Quick smoke test (no UI)

```bash
source .venv/bin/activate
python scripts/e2e_smoke_test.py
```

> Browser renderers live in `orchestrator/src/orchestrator/ui/chat.py` (vanilla JS). React components in `orchestrator/ui/` are used by LangGraph Studio when running `langgraph dev`.

---

## CLI reference

After `pip install -e .`, the `cognilance` command is available. Run `cognilance` with no arguments to print built-in help.

The CLI is for **local development and operations** — running workers/delegators and inspecting the marketplace. Start the registry separately via **[`registry/`](registry/)**. `CognilanceManager` has no CLI command; the [orchestrator](#orchestrator-generative-ui) uses it directly in Python.

### Command overview

| Command | Purpose |
|---------|---------|
| `run` | Start a worker or delegator as a blocking A2A server |
| `chat` | Start a worker or delegator with an interactive prompt loop |
| `discover` | List agents currently registered in the marketplace |
| `info` | Show full details for one agent by ID |
| `register` | List an externally-hosted worker/delegator on the registry |

### Registry

Start the registry separately — see [Registry](#registry) for Docker, SQLite, and API details.

```bash
cd registry && docker compose watch
# API: http://127.0.0.1:8088  ·  Dashboard: http://127.0.0.1:8088/dashboard
```

---

### `cognilance run`

**Purpose:** Run a `CognilanceWorker` or `CognilanceDelegator` as a production-style A2A server. Blocks until stopped. Other agents and managers hire it via HTTP (`POST /a2a/tasks`).

Requires the registry to be running (unless `--no-register` is passed).

```bash
cognilance run agents/research_agent.py
cognilance run agents/python_code_writer.py --port 8103
cognilance run agents/research_agent.py --host 0.0.0.0 --port 8101 --no-register
```

| Argument / option | Default | Description |
|-------------------|---------|-------------|
| `agent_file` | required | Path to a `.py` file containing a worker or delegator instance |
| `--port`, `-p` | `8000` | Port for the A2A server |
| `--host` | `0.0.0.0` | Host to bind to |
| `--no-register` | off | Skip registry registration (A2A server only) |

The file must define a module-level instance:

```python
worker = CognilanceWorker(name="...", skills=["..."])
# or
delegator = CognilanceDelegator(name="...", skills=["..."])
```

---

### `cognilance chat`

**Purpose:** Run a worker or delegator in **interactive mode** for quick local testing. Starts the A2A server in a background thread, then opens a prompt loop so you can type tasks directly.

Useful while developing handlers without writing a separate client or curl commands.

```bash
cognilance chat agents/research_agent.py
cognilance chat agents/python_code_writer.py --port 8103
cognilance chat agents/research_agent.py --no-register
```

| Argument / option | Default | Description |
|-------------------|---------|-------------|
| `agent_file` | required | Path to a `.py` file containing a worker or delegator instance |
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

**Purpose:** Register a worker or delegator that is **hosted elsewhere** (your own FastAPI app, a cloud deployment, etc.) without running `worker.run()` locally.

Loads metadata (name, skills, description) from the Python file and posts the given public URL to the registry.

```bash
cognilance register agents/research_agent.py --url https://my-agent.example.com
```

| Argument / option | Description |
|-------------------|-------------|
| `agent_file` | Path to the `.py` file defining the worker or delegator |
| `--url` | Public base URL where the agent's A2A endpoints are reachable |

The remote host must still expose `/a2a`, `/a2a/tasks`, and `/health`.

---

## Local development

```bash
# Terminal 1 — registry
cd registry && docker compose watch

# Terminal 2-4 — agents
python agents/research_agent.py
python agents/data_analyst.py
python agents/python_code_writer.py

# Terminal 5 — verify discovery
cognilance discover

# Terminal 6 — orchestrator (chat UI on :8200)
python -m orchestrator
```

---

## Environment variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `COGNILANCE_REGISTRY_URL` | No | `http://127.0.0.1:8088` | Registry URL |
| `COGNILANCE_PORT` | No | `8000` | Default port for workers and delegators |
| `GROQ_API_KEY` | For agents/orchestrator | — | Groq API key used by the agents and the orchestrator |
| `GROQ_MODEL` | No | `llama-3.3-70b-versatile` | Groq model for agents and the orchestrator |

---

## Project layout

```
cognilance/
├── cognilance/              # SDK package
│   ├── __init__.py          # Public exports
│   ├── assets/
│   │   ├── __init__.py      # LOGO_PATH — brand assets
│   │   └── logo.png         # Cognilance logo
│   ├── manager.py           # CognilanceManager
│   ├── config.py            # Env loading and defaults
│   ├── core/
│   │   ├── runtime.py       # CognilanceWorker, CognilanceDelegator
│   │   └── models.py        # Task, AgentCard, TaskResult, enums
│   ├── registry/
│   │   └── client.py        # RegistryClient (HTTP → registry)
│   ├── transport/
│   │   └── a2a.py           # A2AServer + A2AClient
│   └── cli/
│       └── main.py          # cognilance CLI entry point
├── agents/                  # Groq-backed CognilanceWorker agents
│   ├── research_agent.py    # skill: research      → research-sources UI
│   ├── data_analyst.py      # skill: data-analysis → data-chart UI
│   ├── python_code_writer.py  # skill: python-code  → python-code UI
│   ├── requirements.txt
├── orchestrator/            # Python LangGraph supervisor + generative UI
│   ├── langgraph.json       # graphs + ui bundle config (env: ../.env)
│   ├── package.json         # UI bundler deps (for langgraph dev)
│   ├── pyproject.toml
│   ├── src/orchestrator/
│   │   ├── graph.py         # StateGraph: router → hire/general → END
│   │   ├── state.py         # messages + ui + route
│   │   ├── env.py           # loads repo-root .env
│   │   ├── llm.py           # Groq factory + message helpers
│   │   └── nodes/           # router, hire (discover+hire+render), general
│   └── ui/                  # React/TSX generative-UI components
│       ├── index.tsx        # ComponentMap
│       ├── research-sources/
│       ├── data-chart/
│       └── python-code/
├── scripts/
│   ├── start_agents.sh      # run all three agents
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
    CognilanceDelegator,
    TaskContext,   # alias for CognilanceManager in delegator handlers
    Task,
    TaskResult,
    AgentCard,
)
```

---

## License

MIT — see [LICENSE](LICENSE).

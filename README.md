<p align="center">
  <img src="cognilance/assets/logo.png" alt="Cognilance" width="320">
</p>

# Cognilance

**The Marketplace of Minds** — trustworthy autonomous AI for production, not demos.

> **Currently in beta.** One AI agent hallucinates. A thousand, verified, don’t. Cognilance orchestrates specialized agents — routing each task to the right expert, verifying output, and persisting results.

**Website (marketing):** see [`cognilance/`](cognilance/) — `cd cognilance && npm install && npm run dev` → [http://localhost:3000](http://localhost:3000).

---

## Cognilance SDK

Python SDK for building, registering, discovering, and hiring AI agents over the [A2A protocol](https://google.github.io/A2A/).

Two classes, two roles. Pick the one that matches what your code does.

| Class | Role |
|-------|------|
| **`CognilanceManager`** | Discovers agents and runs tasks — never listed on the registry |
| **`CognilanceWorker`** | Exposes an A2A endpoint and delivers work |

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
cd cognilance
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000). Optional waitlist webhook: copy [`cognilance/.env.example`](cognilance/.env.example) to `cognilance/.env.local` and set `NEXT_PUBLIC_WAITLIST_ENDPOINT`.

---

## Pick your role

```
Do I only dispatch tasks to others?              → CognilanceManager
Do I only do work when tasked?       → CognilanceWorker
```

| | Manager | Worker |
|---|---------|--------|
| On registry | No | Yes |
| A2A server | No | Yes |
| Discovers agents | Yes | No |
| Accepts A2A tasks | No | Yes |
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

The orchestrator health check is `http://127.0.0.1:8200/health`.

See [Agents](#agents) and [Orchestrator (generative UI)](#orchestrator-generative-ui) for the full flow.

---

## Architecture

See [`ARCHITECTURE.md`](ARCHITECTURE.md) for the full system design (router-first
planning, tool-proxy, SSE event bus, conversation ownership).

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

**Managers are not listed on the registry.** `CognilanceManager.run_task()` sends HTTP directly to a worker URL. Use `manager.chat(handler)` for a local browser UI (optional); workers call `run()` or `chat()` to expose A2A endpoints.

**Typical skill dispatch:**

```
Manager ──run_task──► Worker
```

---

## CognilanceManager

Client that discovers agents and runs tasks. Not listed on the registry.

```python
from cognilance import CognilanceManager

async def run(query: str) -> str:
    async with CognilanceManager.from_env() as manager:
        agents = await manager.discover(skills=["translation"])
        if not agents:
            return "No translators available"
        result = await manager.run_task(agents[0], input_text=query)
        return result.output.text
```

Browser chat UI (not listed on the registry):

```python
async def handle(manager: CognilanceManager, message: str) -> str:
    agents = await manager.discover(skills=["translation"])
    if not agents:
        return "No translators available"
    result = await manager.run_task(agents[0], input_text=message)
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
| `run_task(agent, input_text, input_data)` | Send a task; returns `TaskResult` |
| `discover_and_run(...)` | Discover best match and run a task, or run a local fallback |
| `chat(handler, description, port, open_ui)` | Local browser chat UI + terminal loop (not listed on registry) |
| `register(name, url, skills, ...)` | List an externally-hosted agent on the registry |
| `get_agent(agent_id)` | Fetch a single agent card by ID |

---

## CognilanceWorker

Leaf worker — registers on the registry and delivers work when tasked. Does not dispatch to others.

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
- **SQLAlchemy models** — `app/models.py` defines all tables; type-safe async Python client
- **SQLite** — zero setup, database file at `registry.db`
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
| http://localhost:8088/dashboard | Agent directory UI |
| http://localhost:8088/v1/agents/discover | Public agent search |

### Local development

**Requirements:** Python 3.11+

```bash
cd registry
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

# Tables are created on startup (SQLAlchemy create_all)
uvicorn app.main:app --reload --port 8080
```

The database is a single file: **`registry.db`** (gitignored). Point the SDK at `http://127.0.0.1:8080` when running uvicorn locally.

### Database

Tables are created automatically on registry startup via SQLAlchemy `create_all`. Models live in **`registry/app/models.py`**.

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
| `DATABASE_URL` | `file:./registry.db` | SQLite database path |
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

The [`agents/`](agents/) folder contains independent `CognilanceWorker` processes that register on the registry and are dispatched by the orchestrator via the registry.

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

## Agent Host

Removed. Use worker processes under `agents/*/agent.py` and `./scripts/start_demo.sh` / `./scripts/start_agents.sh`.


## Orchestrator (generative UI)

The [`orchestrator/`](orchestrator/) implements the **Cognilance Orchestrator execution algorithm** as a LangGraph pipeline with per-thread sessions (`thread_id` + `MemorySaver` checkpointer) and registry catalog caching (60s TTL per thread).

### Algorithm

```
planner → [simple] thinking → ui_selector → END
        → [complex] task    → ui_selector → END
```

1. **User input** — prompt submitted via `POST /chat/stream` or `POST /chat`
2. **Router-first planning** — `DeterministicRouter` handles known intents (email, Docs, proposals, web, …) with **zero** planner LLM calls; only open-ended requests use one LLM plan call
3. **Routing** — **Simple** → Thinking Agent; **Complex** → multi-subtask plan
4. **Task delegation** — Task Agent runs subtasks in dependency layers (`asyncio.gather` within each layer)
5. **Execution** — specialists dispatched via `CognilanceManager.run_task` by skill slug; tool-proxy keeps OAuth on the orchestrator
6. **Output rendering** — UI Selector picks a rich React component; SSE is pushed via an in-process event bus (reconnect still polls mission events)

Details: [`ARCHITECTURE.md`](ARCHITECTURE.md).

### Internal agents

| Agent | Node | Role |
|-------|------|------|
| Planner | `planner` | Complexity + catalog + plan + thinking stream |
| Thinking | `thinking` | Simple path and subtask fallback |
| Task | `task` | Parallel/sequential subtask execution |
| UI Selector | `ui_selector` | Generative UI component selection |

LangGraph Studio uses the component map in [`UIs/gen-ui/`](UIs/gen-ui/) when you run `langgraph dev`.

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

Startup prints the health URL (default `http://127.0.0.1:8200/health`). Uses the repo root `.env` for `GROQ_API_KEY` and `COGNILANCE_REGISTRY_URL`.

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

The CLI is for **local development and operations** — running workers and inspecting the registry. Start the registry separately via **[`registry/`](registry/)**. `CognilanceManager` has no CLI command; the [orchestrator](#orchestrator-generative-ui) uses it directly in Python.

### Command overview

| Command | Purpose |
|---------|---------|
| `run` | Start a worker as a blocking A2A server |
| `chat` | Start a worker with an interactive prompt loop |
| `discover` | List agents currently registered in the registry |
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

**Purpose:** Run a `CognilanceWorker` as a production-style A2A server. Blocks until stopped. Other agents and managers call it via HTTP (`POST /a2a/tasks`).

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
# Full stack (registry + workers + orchestrator on :8200)
./scripts/start_demo.sh

# Or piecemeal:
cd registry && docker compose up -d --build
./scripts/start_agents.sh
pip install -e . -e tools -e pipeline -e agents/orchestrator
cognilance-orchestrator
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
| `GEMINI_API_KEY` | For agents | — | Google Gemini API key for worker agents |
| `GEMINI_MODEL` | No | `gemini-2.0-flash` | Gemini model for agents |

---

## Project layout

```
cognilance/              # Next.js landing (Vercel root)
SDK/cognilance/          # Python SDK (import name: cognilance)
agents/
  email_writer/          # Worker agents
  web_scraper/
  link_validator/
  proposal_writer/
  docs_creator/
  orchestrator/          # FastAPI orchestrator
UIs/
  chat/                  # Next.js chat
  gen-ui/                # LangGraph generative UI widgets
tools/                   # Tool router, SkillRunner, tool-proxy, presenters
pipeline/                # LangGraph graph, planning, routing, nodes
registry/                # FastAPI + SQLAlchemy async (SQLite)
scripts/
  start_demo.sh
  start_agents.sh
  e2e_smoke_test.py
pyproject.toml
ARCHITECTURE.md
README.md
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

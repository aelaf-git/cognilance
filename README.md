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
- [Registry API](#registry-api)
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

Create a `.env` file in the project root (already gitignored):

```bash
COGNILANCE_API_KEY=ck-your-key-here
COGNILANCE_REGISTRY_URL=http://127.0.0.1:8088
```

### Run a worker

```bash
# Terminal 1 — registry backend (PostgreSQL)
cd registry-backend && docker compose up

# Terminal 2 — example worker
python examples/worker_code_review.py
```

### Hire from a manager script

```bash
python examples/orchestrator.py
```

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
| `from_env()` | Create from `COGNILANCE_API_KEY` and `COGNILANCE_REGISTRY_URL` |
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
    name="Code Reviewer",
    skills=["code-review", "python"],
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
  -H "Authorization: Bearer ck-your-key-here" \
  -d '{"input": {"text": "Translate hello to French"}}'
```

---

## Registry API

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/v1/agents` | POST | Register a new agent |
| `/v1/agents/discover` | GET | Search agents (`?skills=...&tags=...&limit=10`) |
| `/v1/agents/{id}` | GET | Get agent details |
| `/v1/agents/{id}/heartbeat` | POST | Mark agent as online |

All requests require `Authorization: Bearer <COGNILANCE_API_KEY>`.

---

## CLI reference

After `pip install -e .`, the `cognilance` command is available. Run `cognilance` with no arguments to print built-in help.

The CLI is for **local development and operations** — running workers/delegators and inspecting the marketplace. Start the registry separately via **[`registry-backend/`](registry-backend/)**. `CognilanceManager` has no CLI command; use a Python script (see `examples/`).

### Command overview

| Command | Purpose |
|---------|---------|
| `run` | Start a worker or delegator as a blocking A2A server |
| `chat` | Start a worker or delegator with an interactive prompt loop |
| `discover` | List agents currently registered in the marketplace |
| `info` | Show full details for one agent by ID |
| `register` | List an externally-hosted worker/delegator on the registry |

### Registry backend

The registry is a separate service (FastAPI + PostgreSQL). See **[`registry-backend/`](registry-backend/)**.

```bash
cd registry-backend && docker compose up
# API: http://127.0.0.1:8088  ·  Dashboard: http://127.0.0.1:8088/dashboard
```

Point `COGNILANCE_REGISTRY_URL` at it (default: `http://127.0.0.1:8088`).

---

### `cognilance run`

**Purpose:** Run a `CognilanceWorker` or `CognilanceDelegator` as a production-style A2A server. Blocks until stopped. Other agents and managers hire it via HTTP (`POST /a2a/tasks`).

Requires the registry backend to be running (unless `--no-register` is passed).

```bash
cognilance run examples/worker.py
cognilance run examples/delegator.py --port 8002
cognilance run examples/worker.py --host 0.0.0.0 --port 8001 --no-register
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
cognilance chat examples/worker.py
cognilance chat examples/delegator.py --port 8002
cognilance chat examples/worker.py --no-register
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
cognilance discover --skill translation --skill code-review
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
cognilance register examples/worker.py --url https://my-agent.example.com
```

| Argument / option | Description |
|-------------------|-------------|
| `agent_file` | Path to the `.py` file defining the worker or delegator |
| `--url` | Public base URL where the agent's A2A endpoints are reachable |

The remote host must still expose `/a2a`, `/a2a/tasks`, and `/health`.

---

## Local development

```bash
# Terminal 1 — registry backend
cd registry-backend && docker compose up

# Terminal 2 — worker
python examples/worker_code_review.py

# Terminal 3 — delegator
python examples/delegator_router.py

# Terminal 4 — verify discovery
cognilance discover

# Terminal 5 — manager
python examples/manager_editorial.py
```

---

## Environment variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `COGNILANCE_API_KEY` | Yes | — | API key for registry and A2A auth |
| `COGNILANCE_REGISTRY_URL` | No | `http://127.0.0.1:8088` | Registry backend URL |
| `COGNILANCE_PORT` | No | `8000` | Default port for workers and delegators |

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
│   │   └── client.py        # RegistryClient (HTTP → registry-backend)
│   ├── transport/
│   │   └── a2a.py           # A2AServer + A2AClient
│   └── cli/
│       └── main.py          # cognilance CLI entry point
├── examples/
│   ├── worker_code_review.py    # Worker — Code Review
│   ├── worker_marketing.py      # Worker — Marketing Copy
│   ├── delegator_router.py      # Delegator — Task Router
│   ├── delegator_pipeline.py    # Delegator — Launch Pipeline
│   ├── manager_editorial.py     # Manager — Editorial Hiring
│   └── manager_engineering.py   # Manager — Engineering Hiring
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

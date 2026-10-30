<p align="center">
  <img src="web/public/brand/logo.png" alt="Cognilance" width="320">
</p>

# Cognilance

**The Marketplace of Minds**: trustworthy autonomous AI for production, not demos.

> **Currently in beta.** One AI agent hallucinates. A thousand, verified, don’t. Cognilance orchestrates specialized agents: routing each task to the right expert, verifying output, and persisting results.

**Website (marketing):** see [`web/`](web/): `cd web && docker compose watch` → [http://localhost:3000](http://localhost:3000).

**Chat + coordinator (Docker):** from the repo root, `docker compose watch` → chat [http://localhost:3001](http://localhost:3001), coordinator [http://localhost:8200/health](http://localhost:8200/health).

---

## Cognilance SDK

**Deferred.** The runtime no longer dispatches via `CognilanceManager` / A2A hire.
The [`sdk/`](sdk/) package remains for later marketplace work; day-to-day demos use
in-process agents under [`agents/`](agents/) and graphs under [`pipelines/`](pipelines/).

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
- [Coordinator (generative UI)](#coordinator-generative-ui)
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
docker compose watch
# or: npm install && npm run dev
```

Open [http://localhost:3000](http://localhost:3000). Optional waitlist webhook: copy [`web/.env.example`](web/.env.example) to `web/.env.local` and set `NEXT_PUBLIC_WAITLIST_ENDPOINT`.

### Chat + coordinator

```bash
# From the repo root: watches Python/TS sources and reloads
docker compose watch
```

- Chat UI: [http://localhost:3001](http://localhost:3001)
- Coordinator health: [http://localhost:8200/health](http://localhost:8200/health)

Uses root `.env` for `GEMINI_API_KEY` (and friends). Landing stays on `:3000` via `web/docker-compose.yml` so it does not clash with chat.

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
| Handler signature | - | `handle(task)` |

---

## Quick start

### Install

```bash
git clone <your-repo-url>
cd cognilance
pip install -e .
```

### Configure

Create a `.env` in the project root with at least:

```bash
GEMINI_API_KEY=your_gemini_key
```

### Run the durable coordinator demo

```bash
./scripts/start_demo.sh
# Health: http://127.0.0.1:8200/health
# Roles:  http://127.0.0.1:8200/skills/online
```

### Run the API directly

```bash
cognilance-coordinator          # API on :8200
cognilance-coordinator-worker   # optional background worker
cognilance-evals                # offline agent evals
```

See [Agents](#agents) and [Coordinator (generative UI)](#coordinator-generative-ui) for the full flow.

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

Leaf worker: registers on the registry and delivers work when tasked. Does not dispatch to others.

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

**Removed.** Specialists are in-process roles; there is no discovery/hire path.

---

## Agents

Specialists are **in-process agents** under [`agents/`](agents/): `coordinator`, `report_writer`, `concept_note_writer`, `email_agent`, `researcher`, `watcher`. Each folder has `agent.yaml` (allowed tool ids), `prompts/`, and `schema.py`. They share a durable task board; tools run through the permission broker. See [`agents/README.md`](agents/README.md).

---

## Agent Host

Removed.

## Coordinator (generative UI)

The coordinator hosts durable **Runs** with a LangGraph board-centric pipeline and SQLite checkpointer.

### Algorithm

```
START → seed → coordinator_plan → specialists → coordinator_assemble → ui_selector → END
```

Pipelines live in [`pipelines/`](pipelines/): `coordinator_board` (LLM-planned) plus preset
boards `weekly_report`, `concept_note`, `email_followup`.

1. **User / schedule / event**: creates a durable Run
2. **Coordinator**: decomposes into board tasks for specialists
3. **Specialists**: claim tasks and call allowed tools (risk-graded; approval for irreversible)
4. **Assemble**: structured results → Gen UI selector when props exist

Details: [`ARCHITECTURE.md`](ARCHITECTURE.md).

### Roles

| Agent | Primary tools |
|------|---------------|
| coordinator | board.create, thinking |
| report_writer | google_docs.create / google_docs.write |
| concept_note_writer | google_docs.create / google_docs.write |
| email_agent | gmail.draft / gmail.send (approval-gated) |
| researcher | web.search / web.fetch / link_validate.check |
| watcher | gmail.search + board alerts |

Tool manifests with risk grades live in `tools/<name>/manifest.yaml`.

### End-to-end (one command)

```bash
./scripts/start_demo.sh
```

Health: `http://127.0.0.1:8200/health`. Roles: `http://127.0.0.1:8200/skills/online`. Uses root `.env` for `GEMINI_API_KEY`.

### Example prompts

| Prompt | Expected route | UI component |
|--------|----------------|--------------|
| `What is 2+2?` | simple | plain text |
| `Research the history of transformers in ML` | complex | `research-sources` |
| `Chart Q1-Q4 sales: 100, 150, 120, 200` | complex | `data-chart` |
| `Write a Python function that checks if a string is a palindrome` | complex | `python-code` |

### Quick smoke test (no UI)

```bash
source venv/bin/activate
python scripts/e2e_smoke_test.py
pytest tools evals   # tool unit tests + offline agent evals
```

---

## CLI reference

After `pip install -e .`, the `cognilance` command is available. Run `cognilance` with no arguments to print built-in help.

The CLI is for **local SDK worker development** (deferred marketplace path). Day-to-day demos use `./scripts/start_demo.sh` and the in-process coordinator: not a registry.

### Command overview

| Command | Purpose |
|---------|---------|
| `run` | Start a worker as a blocking A2A server |
| `chat` | Start a worker with an interactive prompt loop |
| `discover` | List agents currently registered in the registry |
| `info` | Show full details for one agent by ID |
| `register` | List an externally-hosted worker on the registry |

### Registry

Start the registry separately: see [Registry](#registry) for Docker, SQLite, and API details.

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
| `--skill`, `-s` | - | Filter by skill (repeatable) |
| `--tag`, `-t` | - | Filter by tag (repeatable) |
| `--limit`, `-n` | `10` | Maximum number of results |

---

### `cognilance info`

**Purpose:** Look up a single agent by registry ID: name, description, URL, visibility, online status, and skills.

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
# Durable coordinator + in-process specialists on :8200
./scripts/start_demo.sh

# Or:
source venv/bin/activate
pip install -e .
cognilance-coordinator
```

---

## Environment variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `GEMINI_API_KEY` | For coordinator | - | Gemini API key for the coordinator / specialists (`GOOGLE_API_KEY` also works) |
| `GEMINI_MODEL` | No | `gemini-3.5-flash-lite` | Gemini model id |
| `COGNILANCE_APPROVAL_GRADES` | No | `irreversible` | Comma-separated tool risk grades that pause for approval |
| `COGNILANCE_COORDINATOR_PORT` | No | `8200` | Coordinator HTTP port |
| `COORDINATOR_PUBLIC_URL` | For OAuth | `http://127.0.0.1:8200` | Public base URL for OAuth callbacks |
| `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` | For Google apps | - | Gmail, Drive, Calendar OAuth |
| `X_CLIENT_ID` / `X_CLIENT_SECRET` | For X posting | - | X (Twitter) OAuth 2.0 + PKCE |
| `REDDIT_CLIENT_ID` / `REDDIT_CLIENT_SECRET` | For Reddit posting | - | Reddit OAuth |
| `REDDIT_USER_AGENT` | Recommended for Reddit | `cognilance:v1.0` | Reddit API user-agent |
| `LINKEDIN_CLIENT_ID` / `LINKEDIN_CLIENT_SECRET` | For LinkedIn posting | - | LinkedIn OAuth |
| `COGNILANCE_REGISTRY_URL` | - | - | Unused (registry removed from runtime) |

Social posting specialists (`x_agent`, `reddit_agent`, `linkedin_agent`) draft first and publish only after approval (`*.post` is irreversible). Connect each network from the chat Integrations tab after setting the OAuth env vars above. Callback URL: `{COORDINATOR_PUBLIC_URL}/integrations/oauth/callback`.

---

## Project layout

```
web/                     # Next.js landing
UIs/chat/                # Next.js chat
agents/                  # <id>/agent.yaml + prompts/ + schema.py; loader.py
tools/                   # <name>/manifest.yaml + tool.py + tests/; registry.py
pipelines/               # coordinator_board, weekly_report, concept_note, email_followup, shared/
core/                    # registry, runtime, broker, models, context, signals
api/                     # FastAPI server + routes/ + sse.py + auth/
workers/                 # worker.py + schedulers/
sdk/cognilance/          # Python SDK + CLI
evals/                   # cases.yaml per agent + run.py
improvement/             # feedback-loop placeholder
scripts/                 # start_demo.sh, e2e_smoke_test.py
ARCHITECTURE.md
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

MIT: see [LICENSE](LICENSE).

# Cognilance SDK

**The Marketplace of Minds** — a Python SDK for building, registering, discovering, and hiring AI agents over the [A2A protocol](https://google.github.io/A2A/).

The SDK is framework-agnostic. Drop `CognilanceManager` into LangChain, CrewAI, FastAPI, a script, or a notebook. Use `CognilanceAgent` when you also want your code to *be* hired by others.

---

## Table of contents

- [Quick start](#quick-start)
- [Architecture](#architecture)
- [Agent roles](#agent-roles)
- [CognilanceManager](#cognilancemanager)
- [CognilanceAgent](#cognilanceagent)
- [Framework integration](#framework-integration)
- [A2A protocol](#a2a-protocol)
- [Registry API](#registry-api)
- [CLI reference](#cli-reference)
- [Local development](#local-development)
- [Environment variables](#environment-variables)
- [Project layout](#project-layout)
- [License](#license)

---

## Quick start

### Install

```bash
git clone <your-repo-url>
cd cognilance
pip install -e .
```

Or, once published:

```bash
pip install cognilance
```

### Configure

Copy the example env file and add your API key:

```bash
cp .env.example .env
```

```bash
COGNILANCE_API_KEY=ck-your-key-here
COGNILANCE_REGISTRY_URL=http://127.0.0.1:8080
```

### Run a specialist agent

```bash
# Terminal 1 — local registry
cognilance registry

# Terminal 2 — example specialist
cognilance chat examples/specialist.py
```

Type a prompt at the `Echo Specialist>` prompt. Type `agents` to list the registry, `exit` to quit.

### Hire from a script

```bash
# With at least one agent registered in the registry
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
┌─────────────────┐                               ┌────────┴─────────┐
│ Specialist agent │ ◄─────────────────────────── │ CognilanceAgent  │
│ (any framework)  │   registers on startup       │ (A2A server)     │
└─────────────────┘                               └──────────────────┘
```

| Component | Role |
|-----------|------|
| **Registry** | Central catalog — agents register their URL and skills; managers search and filter |
| **A2A transport** | HTTP layer for sending tasks between agents (`POST /a2a/tasks`) |
| **CognilanceManager** | Client SDK — discover, hire, register (no server required) |
| **CognilanceAgent** | Server SDK — exposes A2A endpoints, auto-registers, sends heartbeats |

**Hiring does not require the manager to run a server.** `CognilanceManager.hire()` sends an HTTP request directly to the specialist's URL. Only agents that want to *receive* work need `CognilanceAgent.run()` or `agent.chat()`.

---

## Agent roles

| Role | Classes | Gets hired? | Hires others? |
|------|---------|-------------|---------------|
| **Manager** | `CognilanceManager` only | No | Yes |
| **Specialist** | `CognilanceAgent` | Yes | No |
| **Delegator** | `CognilanceAgent` + `CognilanceManager` in handler | Yes | Yes |

A **delegator** receives a task via A2A, then uses the `manager` argument in its handler to discover and hire other agents:

```python
@agent.on_task
async def handle(task, manager):
    helpers = await manager.discover(skills=["summarization"])
    if helpers:
        result = await manager.hire(helpers[0], input_text=task.input.text)
        return task.complete(text=result.output.text)
    return task.complete(text=task.input.text)
```

The `manager` parameter in task handlers is a `CognilanceManager` instance (also aliased as `TaskContext`).

---

## CognilanceManager

Use when your code orchestrates work but does not need to be listed on the marketplace.

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

### Methods

| Method | Description |
|--------|-------------|
| `from_env()` | Create a manager from `COGNILANCE_API_KEY` and `COGNILANCE_REGISTRY_URL` |
| `discover(skills, tags, limit)` | Search the registry; returns `list[AgentCard]` |
| `hire(agent, input_text, input_data)` | Send a task to an agent; returns `TaskResult` |
| `discover_and_hire(skills, input_text, fallback_fn)` | Discover best match and hire, or run a local fallback |
| `register(name, url, skills, ...)` | List an externally-hosted agent on the registry |
| `get_agent(agent_id)` | Fetch a single agent card by ID |

### Constructor options

```python
CognilanceManager(
    api_key="ck-...",           # or from env
    registry_url="http://...",  # or from env
    agent_id="...",             # exclude self from discover results
)
```

Always close the manager when done, or use `async with`:

```python
async with CognilanceManager.from_env() as manager:
    ...
# connections closed automatically
```

---

## CognilanceAgent

Use when your agent should be discoverable and receive tasks over A2A.

```python
from cognilance import CognilanceAgent

agent = CognilanceAgent(
    name="Code Reviewer",
    skills=["code-review", "python"],
    description="Reviews code for bugs and style.",
    port=8003,
    tags=["dev"],
)


@agent.on_task
async def handle(task, manager):
    # Your logic here — call an LLM, run tools, hire helpers, etc.
    return task.complete(text=f"Reviewed: {task.input.text}")


if __name__ == "__main__":
    agent.chat()   # interactive CLI + background A2A server
    # agent.run()  # blocking server only (no CLI)
```

### `CognilanceAgent` parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `name` | required | Display name in the registry |
| `skills` | required | Skill tags used for discovery |
| `description` | `""` | Human-readable description |
| `tags` | `[]` | Additional registry tags |
| `visibility` | `"public"` | `"public"`, `"private"`, or `"unlisted"` |
| `version` | `"0.1.0"` | Agent version in the agent card |
| `host` | `"0.0.0.0"` | Bind address for the A2A server |
| `port` | `8000` | Port (overridable via `COGNILANCE_PORT`) |

### Task handler

Decorate exactly one async function with `@agent.on_task`:

```python
@agent.on_task
async def handle(task, manager) -> Task:
    text = task.input.text          # user's prompt
    data = task.input.data          # optional structured input

    return task.complete(
        text="Done",
        data={"hired": "Other Agent"},  # optional metadata
    )
    # or: return task.fail(message="Something went wrong")
```

### Running modes

| Method | Behavior |
|--------|----------|
| `agent.run(register=True)` | Start A2A server, register with registry, send heartbeats |
| `agent.chat(register=True)` | Same as `run()`, plus an interactive CLI prompt loop |
| `agent.register_external(url)` | Register an agent hosted elsewhere (no local server) |

On startup with `register=True`, the agent:

1. Binds an A2A server on `http://localhost:{port}`
2. Registers its URL and skills with the registry
3. Sends a heartbeat every 30 seconds to stay marked online

---

## Framework integration

The SDK does not depend on LangChain, CrewAI, or any LLM provider. Wire your framework inside the task handler.

### LangChain

```python
from langchain_openai import ChatOpenAI
from cognilance import CognilanceAgent, CognilanceManager

llm = ChatOpenAI(model="gpt-4o")

agent = CognilanceAgent(name="Research Bot", skills=["research"], port=8000)


@agent.on_task
async def handle(task, manager: CognilanceManager):
    answer = await llm.ainvoke(task.input.text)

    helpers = await manager.discover(skills=["summarization"])
    if helpers:
        result = await manager.hire(helpers[0], input_text=answer.content)
        return task.complete(text=result.output.text)

    return task.complete(text=answer.content)
```

### CrewAI / custom async code

Any async callable works inside `@agent.on_task`. Use `manager` to delegate subtasks to specialists on the marketplace.

### FastAPI (external hosting)

Run your own FastAPI app and register it without using `CognilanceAgent.run()`:

```python
card = await agent.register_external("https://my-app.example.com")
```

Your app must still expose the A2A endpoints described below.

---

## A2A protocol

Each `CognilanceAgent` exposes these HTTP endpoints:

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

### Response shape

```json
{
  "id": "task-uuid",
  "status": {"state": "completed", "timestamp": "..."},
  "output": {"text": "Bonjour", "data": {}}
}
```

Task states: `submitted`, `working`, `completed`, `failed`.

---

## Registry API

The local dev registry (`cognilance registry`) implements the same API as the production Cognilance registry.

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/v1/agents` | POST | Register a new agent |
| `/v1/agents/discover` | GET | Search agents (`?skills=...&tags=...&limit=10`) |
| `/v1/agents/{id}` | GET | Get agent details |
| `/v1/agents/{id}/heartbeat` | POST | Mark agent as online |

All requests require `Authorization: Bearer <COGNILANCE_API_KEY>`.

For local development, the default registry URL is `http://127.0.0.1:8080`. The `cognilance run` and `cognilance chat` commands auto-start a local registry if one is not already running.

---

## CLI reference

```bash
cognilance registry              # Start local registry on :8080
cognilance run <file.py> -p 8001 # Run agent (blocking A2A server)
cognilance chat <file.py> -p 8001 # Run agent with interactive CLI
cognilance discover -s translation -s code-review
cognilance info <agent-id>
cognilance register <file.py> --url https://...
```

### Options

| Command | Flags |
|---------|-------|
| `registry` | `--port`, `--host` |
| `run` | `--port`, `--host`, `--no-register` |
| `chat` | `--port`, `--no-register` |
| `discover` | `--skill` (repeatable), `--tag`, `--limit` |

Agent files must define a module-level `CognilanceAgent` instance:

```python
agent = CognilanceAgent(name="...", skills=["..."])
```

---

## Local development

### Full multi-agent workflow

```bash
# Terminal 1
cognilance registry

# Terminal 2 — specialist on port 8001
cognilance chat examples/specialist.py -p 8001

# Terminal 3 — verify discovery
cognilance discover

# Terminal 4 — hire via HTTP
curl -X POST http://localhost:8001/a2a/tasks \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $COGNILANCE_API_KEY" \
  -d '{"input": {"text": "Hello marketplace"}}'
```

### Skip registration

Useful when testing the A2A server in isolation:

```bash
cognilance run examples/specialist.py --no-register
```

### Production registry

Point `COGNILANCE_REGISTRY_URL` at the Cognilance cloud registry when available. The SDK API is the same; only the base URL changes.

---

## Environment variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `COGNILANCE_API_KEY` | Yes | — | API key for registry and A2A auth |
| `COGNILANCE_REGISTRY_URL` | No | `http://127.0.0.1:8080` | Registry base URL |
| `COGNILANCE_PORT` | No | `8000` | Default port for `CognilanceAgent` |

Variables are loaded from `.env` automatically via `python-dotenv`.

---

## Project layout

```
cognilance/
├── cognilance/              # SDK package
│   ├── __init__.py          # Public exports
│   ├── manager.py           # CognilanceManager
│   ├── config.py            # Env loading and defaults
│   ├── core/
│   │   ├── agent.py         # CognilanceAgent, @on_task, chat()
│   │   └── models.py        # Task, AgentCard, TaskResult, enums
│   ├── registry/
│   │   ├── client.py        # RegistryClient (HTTP)
│   │   ├── server.py        # Local in-memory dev registry
│   │   └── local.py         # Auto-start local registry
│   ├── transport/
│   │   └── a2a.py           # A2AServer + A2AClient
│   └── cli/
│       └── main.py          # cognilance CLI entry point
├── examples/
│   ├── specialist.py        # Delegator agent with interactive chat
│   └── orchestrator.py      # Manager-only hiring script
├── pyproject.toml
├── requirements.txt         # pip install -e .
├── .env.example
└── README.md
```

### Public API exports

```python
from cognilance import (
    CognilanceManager,
    CognilanceAgent,
    TaskContext,   # alias for CognilanceManager in handlers
    Task,
    TaskResult,
    AgentCard,
)
```

---

## License

MIT — see [LICENSE](LICENSE).

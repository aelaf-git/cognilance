# Agent ZIP template for Cognilance Agent Host

Use this folder as a starting point when building agents for the **Developer Portal** (`http://127.0.0.1:8300`).

## ZIP contract

Your upload must be a `.zip` file (max 15 MB) containing:

| File | Required | Purpose |
|------|----------|---------|
| `*.py` with `CognilanceWorker` | Yes | Agent entry — same pattern as built-in agents in `agents/` |
| `cognilance.json` | No | Manifest: `{ "entry": "agent.py", "name": "My Agent" }` |
| `requirements.txt` | No | Extra pip deps (installed into the **repo venv** before start) |

## Entry file

Define a top-level `CognilanceWorker` instance:

```python
from cognilance import CognilanceWorker

worker = CognilanceWorker(
    name="My Agent",
    skills=["my-skill"],
    description="What this agent does",
    port=8104,  # overridden by Agent Host when started
)

@worker.on_task
async def handle(task):
    return task.complete(text="Hello!")

if __name__ == "__main__":
    worker.run()
```

The host launches agents with:

```bash
cognilance run <entry> --port <allocated> --host 0.0.0.0
```

So hardcoded ports in your file are **overridden** — use a unique **skill** name so the orchestrator hires your agent instead of a built-in.

## Environment

Configure secrets in the **Developer Portal** when uploading an agent (or later via **Secrets** while the agent is stopped).

| Behavior | Detail |
|----------|--------|
| **UI** | Key/value rows — values use password fields |
| **Storage** | Encrypted at rest (Fernet) in Agent Host SQLite |
| **API** | Only variable **names** are returned — never values |
| **At runtime** | Decrypted and injected into the agent subprocess only |
| **Reserved** | `COGNILANCE_PORT` and `COGNILANCE_REGISTRY_URL` are set by the host |

Set `AGENT_HOST_ENCRYPTION_KEY` in the repo `.env` (or reuse `INTEGRATION_ENCRYPTION_KEY`) so secrets remain decryptable across restarts.

Common keys: `GROQ_API_KEY`, `GROQ_MODEL`.

## Build a ZIP from this template

```bash
cd agents/template_agent
zip -r ../template_agent.zip .
```

Or upload `agents/template_agent.zip` from the repo (pre-built).

## Local workflow

1. Start registry: `cd registry && docker compose watch`
2. Start Agent Host: `scripts/start_agent_host.sh`
3. Open `http://127.0.0.1:8300` — upload ZIP, click **Start**
4. Confirm on registry dashboard (`http://127.0.0.1:8088/dashboard`)
5. Start orchestrator and ask for a task matching your skill

## Security note

The Agent Host runs uploaded Python on your machine with **no sandbox**. Use only for local development.

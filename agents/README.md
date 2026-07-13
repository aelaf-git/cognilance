# Cognilance Agents

Each agent lives in its own folder under `agents/`:

```
agents/
  email_writer/
    agent.py           # CognilanceWorker entry
    proxy.py           # orchestrator callback client
    requirements.txt   # agent-specific deps
    cognilance.json    # optional manifest (Agent Host uploads)
    README.md
```

## Email Writer

See [`email_writer/README.md`](email_writer/README.md).

```bash
pip install -e . -r agents/email_writer/requirements.txt
python agents/email_writer/agent.py
```

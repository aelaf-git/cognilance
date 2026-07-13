# Email Writer Agent

Skill: `email-writing` · Port: `8101`

Independent `CognilanceWorker` using Groq for composition and orchestrator Gmail proxy for send/read.

## Run

```bash
pip install -e ../../. -r requirements.txt
python agent.py
```

Requires `GROQ_API_KEY` in `agents/email_writer/.env`,
registry on `:8088`, and orchestrator with Gmail connected.

Optional: `GROQ_MODEL` (default `llama-3.3-70b-versatile`).

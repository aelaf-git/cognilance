# Email Writer Agent

Skill: `email-writing` · Port: `8101`

Independent `CognilanceWorker` using Gemini for composition and orchestrator Gmail proxy for send/read.

## Run

```bash
pip install -e ../../. -r requirements.txt
python agent.py
```

Requires `GEMINI_API_KEY` in the repo root `.env`, registry on `:8088`, and orchestrator with Gmail connected.

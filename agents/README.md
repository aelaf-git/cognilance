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
  web_scraper/
    agent.py           # CognilanceWorker entry
    scrape.py          # search / fetch / clean helpers
    requirements.txt
    cognilance.json
    README.md
  link_validator/
    agent.py           # CognilanceWorker entry
    validate.py        # concurrent link check helpers
    requirements.txt
    cognilance.json
    README.md
```

Every agent loads only its own `agents/<name>/.env` (gitignored). Put `GROQ_API_KEY`
there. The planner hires agents by skill from the registry catalog — there is no
force-hire; keep the agent running so it shows as online.

## Run all agents

With the registry up:

```bash
./scripts/start_agents.sh
```

Discovers every `agents/*/agent.py` (Email Writer, Web Scraper, Link Validator,
and any you add later), installs each agent's requirements, starts them from
their own folder, and waits on health checks. Ctrl+C stops all of them.

## Email Writer

Skill `email-writing`, port `8101`. See [`email_writer/README.md`](email_writer/README.md).

```bash
pip install -e . -r agents/email_writer/requirements.txt
python agents/email_writer/agent.py
```

## Web Scraper

Skill `web-scraping`, port `8102`. See [`web_scraper/README.md`](web_scraper/README.md).

```bash
pip install -e . -r agents/web_scraper/requirements.txt
python agents/web_scraper/agent.py
```

## Link Validator

Skill `link-validation`, port `8103`. See [`link_validator/README.md`](link_validator/README.md).
Deterministic HTTP checks + Groq report. On broken links, the orchestrator re-hires
the responsible agent with the validator's correction request, then re-validates.

```bash
pip install -e . -r agents/link_validator/requirements.txt
python agents/link_validator/agent.py
```

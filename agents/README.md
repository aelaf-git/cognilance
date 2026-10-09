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
  docs_creator/
    agent.py           # CognilanceWorker entry
    proxy.py           # orchestrator Docs proxy client
    requirements.txt
    cognilance.json
    README.md
  proposal_writer/
    agent.py           # CognilanceWorker entry
    proxy.py           # orchestrator Docs proxy client
    docs_ir.py         # proposal/report IR → Docs requests
    charts.py          # matplotlib ChartSpec → PNG
    requirements.txt
    cognilance.json
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

Discovers every `agents/*/agent.py` (Email Writer, Docs Creator, Proposal Writer,
Web Scraper, Link Validator, and any you add later), installs each agent's requirements, starts
them from their own folder, and waits on health checks. Ctrl+C stops all of them.

## Email Writer

Skill `email-writing`, port `8101`. See [`email_writer/README.md`](email_writer/README.md).

```bash
pip install -e . -r agents/email_writer/requirements.txt
python agents/email_writer/agent.py
```

## Proposal Writer

Skill `proposal-writing`, port `8104`. See [`proposal_writer/README.md`](proposal_writer/README.md).
Long-form Google Docs proposals/reports with native tables and matplotlib chart images.
Requires Google Drive connected in the orchestrator.

```bash
pip install -e . -r agents/proposal_writer/requirements.txt
python agents/proposal_writer/agent.py
```

## Docs Creator

Skill `docs-creating`, port `8105`. See [`docs_creator/README.md`](docs_creator/README.md).
Creates an empty titled Google Doc (no body). Requires Google Drive connected.

```bash
pip install -e . -r agents/docs_creator/requirements.txt
python agents/docs_creator/agent.py
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

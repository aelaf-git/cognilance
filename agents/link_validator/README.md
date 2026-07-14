# Link Validator Agent

Skill: `link-validation` · Port: `8103`

Independent `CognilanceWorker` that verifies URLs are functional: concurrent
HEAD/GET checks with redirects, status classification (ok / warning / broken),
and response times. Groq turns the raw check results into a friendly markdown
report and — when links are broken — a `correction_request` instruction that the
orchestrator uses to re-hire the responsible agent to fix its output.

Links are collected from (in order):

1. The request text (plain URLs, markdown links, HTML hrefs)
2. Structured input (`urls`, `links`, `sources`, or an email `body`)
3. Earlier conversation messages ("check those links")

Output data: `summary`, per-link `results`, `sources` (for the `research-sources`
UI card), `broken_links`, `correction_request`, and `status`
(`ok` / `issues_found` / `no_links`).

## Correction loop

When this agent reports `status=issues_found`, the orchestrator re-hires the agent
whose output supplied the links (e.g. the Web Scraper) with the
`correction_request`, then re-validates the corrected output — one round, no
infinite loops.

## Run

```bash
pip install -e ../../. -r requirements.txt
python agent.py
```

Requires `GROQ_API_KEY` in `agents/link_validator/.env` and the registry on
`:8088`. Without a key the agent still works — it falls back to a deterministic
report. Optional: `GROQ_MODEL` (default `llama-3.3-70b-versatile`).

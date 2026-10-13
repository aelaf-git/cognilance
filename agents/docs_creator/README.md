# Docs Creator Agent

Skill: `docs-creating` · Port: `8105`

Creates an **empty** Google Doc with the requested title. It does not write
body text — use Proposal Writer for long-form proposals/reports.

## Run

```bash
pip install -e ../../. -r requirements.txt
python agent.py
```

Requires registry on `:8088` and orchestrator with **Google Drive** connected.

## Example prompts

- “Create a Google Document titled Snow White. I will write a story on it.”
- “Make a blank Google Doc named Meeting Notes”

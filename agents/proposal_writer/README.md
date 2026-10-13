# Proposal Writer Agent

Skill: `proposal-writing` · Port: `8104`

Independent `CognilanceWorker` that composes long-form **proposals and reports** with
Groq and publishes them to **Google Docs** through the orchestrator Docs proxy
(user OAuth — the agent never holds Google tokens).

Documents support:

- Title / subtitle and H1–H3 sections
- Paragraphs and bullets (never Markdown — Docs named styles only)
- Native Docs tables
- Charts as PNG images (matplotlib bar / line / pie from numeric data)
- Inserted images from a URL or Drive file id (no image generation)
- **Surgical section edits**: on “expand/revise Executive Summary”, the agent
  reads the live Doc, replaces only that section’s body, and leaves the rest alone
- **Alignment / paragraph style**: “make it justified” applies real Docs
  `updateParagraphStyle`; if already justified, the agent says so and skips the no-op
- **Always live-read**: when a `document_id` is known, every turn starts with
  `docs_read` and hydrates IR from the Doc so manual edits in the chat Docs pane
  are not overwritten by stale drafts

## Run

```bash
pip install -e ../../. -r requirements.txt
python agent.py
```

Requires:

- `GROQ_API_KEY` in `agents/proposal_writer/.env`
- Registry on `:8088`
- Orchestrator with **Google Drive** connected (Docs scopes)
- Optional: `GROQ_MODEL` (default `openai/gpt-oss-120b`)

## Example prompts

- “Write a proposal for Acme Corp for a 6-week website rebuild at $24k with a pricing table”
- “Create a report with a bar chart of Q1–Q4 fees: 10, 14, 12, 18”
- “Revise the pricing section and update the Google Doc”
- “Preview the document as plain text”

## Notes

- Callbacks go to `/tools/docs/*` with a short-lived grant issued when the
  orchestrator hires `proposal-writing`.
- Connect Google Drive under the orchestrator Integrations page first.

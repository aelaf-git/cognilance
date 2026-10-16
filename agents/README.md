# Cognilance Agents

One folder per agent. Agents are in-process role packs loaded by `agents/loader.py`;
they never run as separate servers.

```
agents/
  loader.py              # agent.yaml -> RolePack
  coordinator/           # plans the shared task board, assembles results
  report_writer/         # summaries, recurring reports, Google Docs
  concept_note_writer/   # concept notes
  email_agent/           # email drafts / gated sends
  researcher/            # web research + link checks
  watcher/               # monitors -> board alerts
```

Each folder:

```
agent.yaml     id, name, model, tools (allowed tool ids), skills, prompts, schema
prompts/       system.md (+ plan.md / assemble.md for the coordinator)
schema.py      pydantic `Result` for structured outputs
```

Tool ids must exist in `tools/<name>/manifest.yaml`; `core/registry` validates
this at startup.

# improvement/

Placeholder for the feedback loop. Nothing here runs yet.

Inputs already produced by the runtime:

- `core/signals` — `record_step` / `record_feedback` write per-run signals
  (tool picked, risk, approval outcomes, user thumbs up/down).
- `evals/` — per-agent `cases.yaml` plus `cognilance-evals` runner.

Planned flow:

1. Collect signals + failed eval cases per agent.
2. Propose prompt / tool-selection changes in `agents/<id>/prompts`.
3. Re-run `cognilance-evals <agent>`; keep the change only if the pass rate improves.

# Orchestrator loop

Chat runs a bounded ReAct loop. Preset pipelines (`weekly_report`, `concept_note`, `email_followup`) still use the linear task board.

```
seed → think → act → observe → evaluate → (think | grounding) → ui_selector
```

Each turn rebuilds a roster from `agents/*/agent.yaml` and injects it into `think`, along with capabilities no current agent covers (`pipelines/coordinator_board/capabilities.yaml`).

## Actions

Exactly one per iteration:

- `answer_directly` — conversation, reasoning, writing, or general knowledge. No tools.
- `use_tool` — an orchestrator-level tool. None are registered, so an unknown id becomes an error observation.
- `delegate` — one or more independent briefs. Dependent work waits for the next iteration.
- `ask_user` — one question when a required input is missing.
- `finish` — the proposed answer, which then goes through the grounding check.

`delegate` is rejected in code when the agent id is unknown, offline, or the brief has no concrete goal and success criteria. A message that is only a greeting, thanks, or goodbye is answered directly even if the model tries to delegate.

## Delegation

Answer directly when the turn needs no live or private data and no side effect. Delegate when it needs external data, a tool, a side effect, long work, or a specialist's output. A brief carries the goal, relevant context only, constraints, the expected output, success criteria, and a budget. The specialist does not receive the whole chat.

## Evaluation and grounding

After every observation, code checks emptiness, errors, and (when a `result` object is present) the agent schema. An LLM judge runs only for a non-empty result. Verdicts are `accept`, `retry` (once), `reroute`, `ask_user`, and `fail_honestly`. Observation text is fenced as untrusted data.

Before the reply is sent, grounding drops sentences that claim a side effect without an accepted ok observation, cite a URL that never appeared, or repeat an instruction found inside an observation. External claims must cite an accepted observation id.

## Limits

8 iterations, 4 delegations, one retry per subtask, and 90 seconds. Hitting a limit ends the turn with what was actually accepted and what is still unfinished. Thinking is logged on the run (`kind=orchestrator`, with `trace_id`) and is not shown to the user.

## Evals

`evals/orchestrator/cases.yaml` holds the scripted scenarios. `pytest evals/test_orchestrator.py` runs them without network and prints delegation rate, hallucination rate (unsupported claims left in the answer), and average iterations.

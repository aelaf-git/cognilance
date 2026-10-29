# Orchestrator diagnosis

The chat graph is a straight line. `pipelines/shared/build.py` compiles `seed → coordinator_plan → specialists → coordinator_assemble → ui_selector` with no conditional edge. Every user message, including "hey!", becomes board work. The coordinator cannot answer on its own.

## Why delegation is poor

`coordinator_plan` in `pipelines/coordinator_board/coordinator.py` asks for 1–4 specialist tasks. The prompt does list the roster: `_plan_prompt` joins `id` and description from `agents/*/agent.yaml` via `agents/loader.py`. That list is a process-lifetime cache, not a status-aware registry. Entries omit required inputs, output shape, limits, and offline status. There is no "not available" list, so a missing capability looks like a planning failure instead of a known gap.

An empty plan is not allowed to stand. The code rewrites it into one `researcher` task whose instruction contains the words "Do not search the web." `specialists._pick_tool` treats the substring `search` as research intent and selects `web.search`. The researcher prompt also prefers tools. So a greeting is forced onto a specialist, and the fallback path can call Google (Serper) even when the prose says not to.

Unknown assignees are dropped in `_validate_assignees`, then the empty-plan fallback invents `researcher` anyway. This process does not read a Postgres agent registry. `core/registry` only validates manifests. A2A hire is deferred (see the README). The live roster is the on-disk manifests, and the planner sees only a thin slice of them.

## Why answers are hallucinated

A specialist may return `SpecialistAction(status="done")` with prose and zero tool observations (`pipelines/coordinator_board/specialists.py`). Assemble then polishes that prose into the user-facing answer. `verify_task_output` checks emptiness, error payloads, and sometimes links. It does not require a claim to trace to an observation, and it does not validate `schema.Result`. A fluent answer with no evidence is shipped. Side effects ("sent", "created") can be stated with no `status=ok` record.

## What has to change

The coordinator needs a loop that can answer, ask, or delegate one validated action, then judge the observation before anything is said to the user. Preset pipelines can keep the linear board. The chat graph cannot.

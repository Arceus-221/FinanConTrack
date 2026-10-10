# Agent pack: how to use

## Install (once)
1. Copy everything in this folder into your project root (keep `.opencode/` and `scripts/`).
2. `git init`, make an initial commit, and set `git config user.name` / `user.email` (the loop commits for you).
3. `opencode models | grep -i google` -> paste three model IDs into `agents.env`
   (MODEL_STRONG = most capable, MODEL_FAST = Flash-class, MODEL_LITE = Flash-Lite-class).
4. Verify OpenCode sees the agents and permissions: `opencode debug agents` and `opencode debug config`.
   Expect planner, implementer, tester, reviewer. If a permission key is rejected, check the
   Agents/Permissions page of the docs for your OpenCode version (V1 and V2 formats differ; V2 reads V1 files).

## Plan (interactive, ~5 prompts, one time)
In the OpenCode TUI switch to the `planner` agent (Tab) and run the spec-kit steps:
`/speckit-constitution`, `/speckit-specify <idea paragraph>`, `/speckit-plan`, `/speckit-tasks`.
Confirm `specs/<feature>/tasks.md` has lines like `- [ ] T001 ... | accept: ...`.
(Invocation syntax can differ per agent; see spec-kit's integrations reference.)

## Build (hands-off)
    ./scripts/run-loop.sh
Per task: implementer -> tester -> reviewer; changes requested = another round (max 4). The script
commits each approved task and ticks it in tasks.md. If the free-tier quota runs out it stops cleanly;
just run it again after the daily reset (state is in the checkboxes).

## Monitor
    ./scripts/status.sh          # counts, recent log, commits, token use per model
    tail -f PROGRESS.md          # live step-by-step log
    .agent-logs/                 # full output of every agent call
Run `uv run pytest -q` yourself now and then: the tester must paste real output, but verify.

## Ship
`git push no-mistakes` (after `no-mistakes init`) for the automated review/test/lint gate and PR.
Run it once at the end: it also spends model calls.

## Count your interventions
Log each manual step in `interventions.md`.

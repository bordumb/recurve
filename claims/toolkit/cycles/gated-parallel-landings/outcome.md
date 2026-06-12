# Outcome: gated-parallel-landings

Closed TK-9. Sculpt: workflows/burndown-parallel.sh (worktree lanes over
disjoint suites; per-landing gap-GREEN + fleet-gate check; revert-and-discard;
orchestrator-owned promotion; landing-less-round watchdog), lanes JSON gained
`dir` for orchestrators, init stamps the template. Gate: integration probe
GREEN (two lanes landed, bad candidate reverted), 9/9 traps RED, fleet gate
green, coverage green. Prose rewritten; v1 sequential remains the default.

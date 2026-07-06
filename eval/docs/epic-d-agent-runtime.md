# Epic D — Agent runtime as a port

**Leverage:** medium (unlocks non-Claude models; small surface).
**Depends on:** nothing. Parallelizable.

> **Prelaunch call: mostly DEFER.** There is exactly one agent runtime today
> (`claude -p`), so the `AgentRuntime` *port + registry* is speculative generality —
> the trap the kernel otherwise avoids. Do the cheap, non-speculative slice now:
> keep all `claude`-specific invocation/pricing/parsing quarantined inside
> `adapters/claude.py` (a clean seam), and have `run_pipeline.py` import it through
> **one** indirection point. Build the actual port (D1–D4) the day you genuinely
> want a cross-runtime result (e.g. "recurve's effect isn't Claude-specific") — a
> real, likely future, but not today's. See the
> [README prelaunch lens](README.md#prelaunch--solo-lens-read-this-before-you-touch-anything).

---

## So what? (plain English)

The "agent" is the model process that actually attempts each task. Today that is
hardwired to Anthropic's `claude -p` CLI. If you ever want to run the *same*
experiment with GPT, Gemini, or a tool like aider — to show recurve's effect
isn't Claude-specific, which is exactly the kind of result reviewers ask for —
you'd have to rewrite the adapter, the price table, and the invocation. There's
no seam to plug a new runtime into. The design *claims* the BYO-agent seam already
makes this provider-agnostic (`eval-full.md:161-165`: "the seam already exists"),
but in code the seam is a single concrete function, not a port with a registry.

## Current state (evidence)

**The invocation is Claude-specific:**

```python
# evallib/adapters/claude.py:30-37
def agent_argv(model, extra=None):
    return ["claude", "-p", "--permission-mode", "bypassPermissions",
            "--model", model, *(extra or [])]        # ← `claude` binary, Claude flags
```

**Budget enforcement reads Claude's JSON report shape:**

```python
# evallib/adapters/claude.py:45-56 — parses `claude -p --output-format json`
d = json.loads(r["stdout"]); ti, to = parse_usage(d); cost = parse_cost(d)
```

**Pricing is a Claude-only table** (`adapters/telemetry.py`, `PRICES_2026_07_04`
prices `claude-*` models; SWE reuses it at `swebench_pipeline.py:64`). Model names
throughout the manifests are Claude ids (`claude-haiku-4-5`, `claude-sonnet-5`).

There is no `AGENT_RUNTIMES` registry and no `agent_runtime` axis in the manifest
— the runtime is implied, never chosen.

## Target design

Mirror the arm-port pattern: an `AgentRuntimePort` with two operations (the two
the harness actually needs — a single-shot solve and a budgeted burndown loop),
a registry keyed by name, and per-runtime usage/cost parsing.

```python
# adapters/runtime.py  (target)
class AgentRuntime(Protocol):
    def run_once(self, model, prompt, workspace, budget_usd) -> RunResult: ...   # bare arms
    def run_budgeted(self, model, prompt_for, workspace, cap, gate_check) -> RunResult: ...  # gated arms
    def parse_usage(self, raw) -> tuple[int,int]: ...
    def parse_cost(self, raw) -> float: ...
    def price(self, model) -> Price: ...

AGENT_RUNTIMES = {"claude": ClaudeRuntime()}     # today's adapters/claude.py, behind the port
def resolve_runtime(name): ...                    # KeyError-with-known-names
```

The manifest gains an optional `[matrix] runtime = "claude"` (default `"claude"`);
`run_pipeline.make_pipeline_adapter` builds `bare_agent`/`gated_agent` from the
resolved runtime instead of importing `adapters.claude` directly
(`run_pipeline.py:56-59`). The watchdog (`watchdog.py`) and budget loop
(`budget.py`) are already runtime-agnostic — they stay shared.

## Tasks

- [ ] **D1 — Define `AgentRuntime` + registry** (`adapters/runtime.py`); wrap
  today's `claude.py` as `ClaudeRuntime`. *Acceptance:* `resolve_runtime("claude")`
  reproduces current behavior; `run_pipeline.py` imports the runtime via the
  registry, not `adapters.claude` by name.

- [ ] **D2 — Move pricing behind the runtime.** `telemetry.PRICES_*` becomes
  `ClaudeRuntime.price`; `estimate_usd` (`cli.py:68`) and SWE's `SWE_MODELS`
  pricing (`swebench_pipeline.py:64`) ask the runtime. *Acceptance:* cost estimates
  unchanged for Claude; a new runtime supplies its own prices.

- [ ] **D3 — Add the manifest `runtime` axis.** Optional, defaults to `"claude"`.
  Validate at plan time (unknown runtime fails loud, same posture as an unknown
  arm). *Acceptance:* omitting the key reproduces today's plans byte-for-byte.

- [ ] **D4 (proof) — Stub a second runtime.** A minimal `openai`/`aider` adapter
  (even mock-only) that runs a mocked cell end-to-end, proving a new runtime is one
  file + one registry line. *Acceptance:* no kernel file changes to add it.

## Risks & constraints

- **The budget model is dollar-based and cache-aware** (`claude.py:1-16` measures
  from the agent's own `total_cost_usd`). A new runtime must expose *real billed
  cost*, not a token estimate, or the spend caps become fiction. If a runtime can't
  report cost, it must price tokens itself and say so.
- **Gated arms drive a recurve burndown** (`make_gated_adapter`,
  `claude.py:75-112`) — that loop is SUT logic, not runtime logic. Keep the split:
  the runtime runs *one* agent invocation; the burndown/gate-check orchestration
  stays in the shared budget loop (and calls the Epic C SUT adapter for the gate).
- **Model-name namespacing.** Once runtimes are plural, `model` ids can collide
  across providers. Consider `runtime:model` in cell ids (`plan.cell_id`,
  `plan.py:35`) if a future matrix mixes providers.

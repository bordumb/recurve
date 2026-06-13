# recurve

**Turn a spec or a README into promises a machine can check — then let an
agent loop build until every promise is proven, without ever un-proving one.**

## So what?

AI agents can write code faster than anyone can review it. The bottleneck
has moved: it's no longer *producing* changes, it's *knowing what's actually
true* about the result. Docs drift, "done" is vibes, and an unattended agent
will happily declare victory on work that doesn't hold up.

recurve fixes the bottleneck by making truth executable:

- Every promise your project makes becomes a **claim** with a small
  executable **probe** that answers GREEN (proven), RED (not yet), or
  BROKEN (couldn't measure — never mistaken for an answer).
- An agent loop picks the most valuable RED claim, makes the smallest change
  that turns it GREEN, and must pass the **full gate** — every previously
  proven claim still GREEN — before the work counts.
- Proven claims keep their probes forever, so nothing regresses silently.
  Each probe also keeps a **trap**: a known-bad input it must reject, so a
  watered-down probe is caught mechanically.
- Decisions that shouldn't be made by a machine (security trade-offs, open
  policy questions) are routed to you, one sentence each. Everything else
  runs unattended.

The result: you review *promises and decisions*; agents own everything
between a RED probe and a green gate; and the code ships with its evidence.

## Install

Requires Python 3.11+. The only dependency (PyYAML) installs automatically.

<details open>
<summary><b>uv</b></summary>

```bash
uv tool install git+https://github.com/bordumb/recurve.git
recurve --help
```

Working from a clone (e.g. to hack on it):

```bash
git clone https://github.com/bordumb/recurve.git
cd recurve
uv tool install --editable .
```

</details>

<details>
<summary><b>pip</b></summary>

```bash
pip install git+https://github.com/bordumb/recurve.git
recurve --help
```

Working from a clone (e.g. to hack on it):

```bash
git clone https://github.com/bordumb/recurve.git
cd recurve
pip install --editable .
```

</details>

Verify the install by running recurve against its own promises — the
toolkit is built with itself, and its claims are probed like anyone else's:

```bash
git clone https://github.com/bordumb/recurve.git && cd recurve
recurve --config recurve.toml matrix --gate
```

## Use it on your project

```bash
cd your-project
/path/to/recurve init --from-repo            # mine your docs/README for promises
# or: recurve init --from-prd spec.md        # decompose a PRD into draft claims
# or: recurve init                           # blank scaffold
```

Then, in order:

1. **Skim the drafts** in `.recurve/claims/<suite>/`. Drafts are guesses
   extracted from prose — your read-through is the quality (and security)
   filter before anything becomes runnable.
2. **Answer the open decisions** in `.recurve/ADJUDICATE.md` — the spots
   where the spec genuinely allows more than one honest answer. One
   sentence each; your choice gets baked into the probe so every future
   agent is bound by it.
3. **Run the baseline:** `recurve baseline <suite>`. Each draft's probe runs
   for real; what's already true files as proven (and guarded from now on),
   what isn't becomes your honest backlog.
4. **Burn it down:** `.recurve/workflows/burndown.sh` drives the loop with
   any agent harness (`burndown.js` if you're on an orchestrator runtime).
   One fresh agent per cycle, full gate after each, work committed
   per-cycle. `RUN.md` is the per-cycle contract either way.

Watch progress any time:

```bash
recurve ledger     # every claim and its status
recurve next       # what the loop will pick next, and why
recurve stats      # close rates, attempts, cost — from the run records
```

## Reports

After every cycle the loop appends a free, deterministic report to
`.recurve/state/reports/<run-id>.md` (also on demand: `recurve report`):
progress by suite, cycle durations with an ETA projection, and an honesty
scan of the diff — suppression markers, sensitive paths to review before
signing. Add `--narrate` to pipe it through any LLM command configured as
`[report] narrator`; the judgment costs whatever your narrator costs, the
numbers stay free.

## What this is

recurve is the toolkit form of a working method: software improves against
its own stated promises, with proof, monotonically.

Every claim lives in three synchronized places, checked against each other:

- **Prose** (`GAPS.md`) — the human-readable promise, for people deciding.
- **Ledger** (`gaps.yaml`) — the machine record, for the loop executing.
- **Probe** (an executable) — the ground truth: exit 0 GREEN, 1 RED,
  anything else BROKEN. The mapping is total; a crash or timeout can never
  masquerade as a verdict.

A few rules carry most of the weight:

- **The ledger records measurements, not intentions.** New claims start as
  drafts; only a real probe run (the baseline) moves them into the ledger,
  with the actual observed output quoted and dated.
- **The ratchet only turns one way.** Closed claims keep their probes as
  regression guards; the gate fails if any of them turns RED, so cycle 12
  cannot quietly undo cycle 3.
- **Probes are guarded too.** Every probe keeps a trap — a counterexample
  fixture it must turn RED. A probe that has never been seen to fail is not
  yet evidence.
- **Fresh agent per cycle; the ledger is the only memory.** No context rot,
  contained failures, and an attempt journal for anything that gets parked,
  so hard-won failure knowledge isn't lost.
- **Humans keep exactly the judgment calls.** Security-sensitive claims are
  review-gated (a green gate is necessary but not sufficient there), open
  policy questions become one-sentence decisions, and the loop's wrap-up
  hands you a short, ranked queue instead of a transcript.

The full design — including the failure-mode catalog the loop is hardened
against (hung probes, stale artifacts, runaway scope, half-finished cycles,
lying dashboards) — is in [docs/plan.md](docs/plan.md).

## The pieces

| Path | What it is |
| --- | --- |
| `recurvelib/` | the engine: config, ledger model, probe runner + traps, freshness, gate matrix, coverage, triage, baseline, locking, parked store, spec decomposition, decision recording, run records, evidence receipts, packs |
| `recurve` | the CLI — `init`, `ledger`, `next`, `probe`, `matrix`, `baseline`, `cycle`, `review`, `park`, `drill`, `stats`, `report`, and friends (`--help` lists all) |
| `schema/` | versioned schemas: gap entry, run record, evidence receipt |
| `templates/` | what `init` stamps into a target: the per-cycle contract (`RUN.md`), unattended runbook, review protocol, troubleshooting, quality presets, burndown workflows, skills |
| `packs/` | claim packs — reusable claim+probe+trap bundles (CLI contract, perf SLO); install as drafts, your baseline measures them |
| `claims/toolkit/` | recurve hosts itself: its own promises, probed and gated |
| `acceptance/` | proof the extraction worked: live side-by-side equivalence with the two projects the method came from, plus end-to-end phase tests |

## Status

All four build phases from [docs/plan.md](docs/plan.md) are complete and
self-hosted:

- **Engine + scaffold** — `init` (blank / from-repo / from-PRD), baseline,
  traps, locking, parked store with attempt journals.
- **Unattended operation** — burndown workflows with the full watchdog set
  (park-and-continue, caps, consecutive-failure and runaway-scope halts),
  schema-validated run records, and a sabotage drill (`recurve drill`) that
  re-introduces a closed defect on a scratch tree to prove the gate catches it.
- **Spec decomposition** — PRD-to-drafts with adversarial twins for every
  claim, severity from the spec's own language, security-relevant claims
  review-gated by default, open questions routed to a decisions file.
- **Leverage** — evidence receipts (hash-chained, pluggable signer),
  `recurve stats` over the run-record dataset, claim packs, multi-target
  federation, and parallel burndown lanes with the gate as the
  serialization point — built by recurve's own loop, three gated cycles.

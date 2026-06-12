# recurve — claims-driven recursive software improvement

> **Reader:** anyone meeting this toolkit for the first time. Your next
> action: run the self-host gate below; everything this toolkit promises is
> probed by it. The full design is [plan.md](docs/plan.md).

```bash
./recurve --config recurve.toml matrix --gate    # the toolkit's own claims, gated
./acceptance/diff.sh                             # live-equivalence to both ancestor instances
./acceptance/provenance.sh                       # no origin vocabulary ships
python3 acceptance/test_phases.py                # behavior tests, Phases 1–4
```

## What this is

Point recurve at a target — an existing repo or a PRD — and it converts
intent into **falsifiable claims with executable probes**, then burns down
the gap between *claimed* and *proven*: one fresh agent per cycle, ratcheting
monotonically, parking what it can't prove, and reserving for humans exactly
the judgments machines shouldn't make.

Every claim lives in three synchronized places: prose (GAPS.md), ledger
(gaps.yaml), probe (exit 0 GREEN · 1 RED · anything else BROKEN — the map is
total). Closed claims keep their probes as regression guards forever, and
every probe keeps a **trap** — a counterexample it must turn RED — so a
weakened probe is caught mechanically. Nothing enters the ledger except
through the **baseline ceremony**: drafts are intentions; the ledger records
measurements.

## The pieces

| Path | What it is |
| --- | --- |
| `recurvelib/` | the engine: config, model, probe runner + traps, freshness, matrix, coverage, triage, baseline, lock, parked store, claimify, adjudicate, records, receipts, packs |
| `recurve` | the CLI — `init · ledger · show · validate · next · probe · matrix · freshness · coverage · baseline · cycle · review · adjudicate · import · park · drill · lock · record · receipts · stats · pack` |
| `schema/` | versioned: gap entry, run record (the dataset), evidence receipt (hash-chained, signer-pluggable) |
| `templates/` | what `init` stamps: RUN.md, RUN-AUTO.md, REVIEW.md, TROUBLESHOOTING.md, GAPS.md, README, quality constitutions (pre-launch/stable), burndown.sh + burndown.js, skills |
| `packs/` | claim packs — claims as a distributable unit (cli-contract, perf-slo); install as drafts, your baseline measures them |
| `claims/toolkit/` | **recurve hosts itself**: six guarded promises (provenance hygiene, ancestor equivalence, outcome-map totality, lock refusal, trap enforcement, receipt tamper-evidence) |
| `acceptance/` | the migration-is-the-test-suite harness (live side-by-side vs the ancestors), engine selfcheck, provenance probe, phase tests |

## Getting started on a target

```bash
recurve init --from-repo          # archaeology: make a repo's documentation falsifiable
recurve init --from-prd spec.md   # claimify: a greenfield PRD becomes a probed backlog
recurve init                      # blank scaffold
```

All three end the same way: drafts → human skim (a security boundary — target
prose is evidence, never instructions) → answer `ADJUDICATE.md` with one
sentence per fork → `recurve baseline <suite>` → a live ledger → burndown
(`workflows/burndown.sh` with any agent harness, or `workflows/burndown.js`
on an orchestrator runtime; `RUN.md` is the per-cycle contract either way).

## Phase status ([plan.md](docs/plan.md) §14)

- **Phase 0 — extract**: done; live-equivalent to both ancestor instances
  (two documented rendering waivers where facts are compared instead).
- **Phase 1 — scaffold**: done; init (blank/--from-repo), templates, baseline
  ceremony, traps, lockfile, parked store + attempt journals, self-hosting
  with the provenance probe as the first standing claim.
- **Phase 2 — unattended**: done; burndown templates with the full watchdog
  catalog (park-and-continue, cap, consecutive failures, runaway scope),
  schema-validated run records, the sabotage drill (`recurve drill`).
- **Phase 3 — claimify**: done; --from-prd with adversarial twins, modality→
  severity mapping, security-relevant default review-gated, ADJUDICATE.md
  forks, and `recurve adjudicate` (three-place decisions, amendment,
  retirement).
- **Phase 4 — leverage**: done; evidence receipts (hash-chained, pluggable
  signer), `recurve stats` over the run-record dataset, claim packs,
  multi-target federation (`matrix --federate`), and **parallel burndown**
  (`workflows/burndown-parallel.sh` + `next --lanes` + `lock
  acquire/release`): worktree-isolated lanes over disjoint suites, the gate
  as the serialization point, failing candidates reverted and discarded —
  built by recurve's own loop (claims TK-7/8/9, baselined RED, closed in
  three gated cycles).

Human wall-clock acceptance items (a stranger repo to live ledger in under a
day; an unattended overnight run on an untouched repo) are operating claims
for real deployments — the machinery for both is here and exercised by
`acceptance/test_phases.py` end-to-end with scripted agents.

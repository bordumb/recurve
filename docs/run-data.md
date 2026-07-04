# Run data & trajectories

Every cycle the loop lands appends one structured record to
`.recurve/state/records.jsonl` — what was attempted, what it cost, what the
gate said. Close rates become triage priors, the history becomes an audit
trail, and the whole log exports as a training-ready dataset whose every reward
names its verifier. **The dataset is the product.**

## The record

A record is schema-validated on append — a malformed record is rejected loudly,
because the dataset stays clean or it is worthless:

```bash
recurve record append   # reads one JSON record on stdin, validates, appends
recurve record list     # the journal, human-readable
```

Beyond the basics (gap, suite, status, attempts, verdict counts before/after),
a record may carry **branches** — the road *not* taken:

```json
"branches": [
  {"kind": "decomposition",
   "description": "split into parser + renderer claims",
   "rejected_because": "renderer half already covered by RND-2"},
  {"kind": "attempt",
   "description": "regex-based extraction",
   "rejected_because": "failed the nested-fixture trap twice"}
]
```

A log of only winners teaches selection nothing. Branch entries preserve the
alternatives a cycle considered and why they lost — labeled failure, the data
most pipelines discard. Each entry requires its `rejected_because`; a branch
without a reason is rejected at append.

## Honest statistics

```bash
recurve stats
```

```text
class               cycles  closed  parked  failed  close%  c%@1  c%@2  avg-attempts  avg-clock
missing-surface          8       8       0       0    100%   88%  100%           1.1       442s

trap debt: 0 waived guards (closed claims the drill cannot audit)
```

Two design choices keep these numbers honest:

- **Budget-attached close rates.** Raw `close%` inflates under retries — a
  class that closes everything in one attempt and a class that closes after
  six look identical. `c%@1` and `c%@2` report the share closed *within an
  attempt budget*, so attempt inflation is visible instead of flattering the
  rate. (In the sample above: 100% closed, but only 88% closed first-try —
  the gap **is** the information.)
- **Trap debt in the same view.** Closed claims carrying `trap_waiver` are
  guards [the drill cannot audit](hardening.md) — that count belongs next to
  the close rates it qualifies, not buried in another command.

## Exporting trajectories

```bash
recurve trajectories                       # verified rows only (default)
recurve trajectories --include-unverified  # everything, marked
```

One JSON object per cycle record on stdout, each row joining the record with
its claim's ledger entry:

```json
{"gap": "CFG-1", "suite": "core", "action": "closed", "attempts": 1,
 "reward": 1, "verified": true, "branches": [],
 "provenance": {"probe": ".../probes/cfg-1.sh", "traps": 2, "trap_waiver": false},
 ...}
```

Three properties are deliberate:

- **Reward provenance on every row.** `reward` is 1 iff the cycle closed its
  claim — and the row names *which probe* decided that and *how many trap
  fixtures* back it. A reward you cannot re-verify is a liability, not a datum.
- **The contamination gate.** A row is **verified** iff its claim still has a
  live probe and at least one non-waived trap. Unverified rows are **excluded
  by default** — training research measured that as little as ~1%
  reward-hacked trajectories in supervised data is enough for models to
  internalize the hack — and re-admitted only by `--include-unverified`,
  marked `"verified": false`. The stderr summary always reports
  exported-vs-excluded counts, so the filtering is itself visible.
- **Determinism.** Stable row order, sorted keys: two exports of the same
  state are byte-identical. An export is diffable evidence, not a one-off
  dump — and the command is read-only by construction.

## What it is for

- **Triage priors** — close rates by class tell the loop (and you) where
  cycles are cheap and where they burn.
- **Audit** — records plus [receipts](evidence.md) reconstruct what happened
  and prove nobody is grading their own homework.
- **Training data** — a trajectory corpus with a grounded,
  falsification-tested reward at every node and branch-level counterfactuals
  is exactly the substrate for learning *which decisions* lead to closed
  claims — with the gate as the filter that keeps the corpus worth learning
  from.

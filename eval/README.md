# eval — the recurve evaluation pipeline

The instrument held to the standard it measures. This pipeline turns an
experiment manifest into pinned cells, runs each through the BYO-agent seam,
grades it against a held-out oracle, and analyzes the results deterministically.
Every stage is a gated claim under recurve's own suite (`.recurve/claims/eval`).

## The design rule

> **Anything that can change a verdict must be pinned and refused-on-drift.
> Anything that can change a timing must be recorded. The manifest is human
> intent; the lock is machine-resolved truth.**

Intent lives in the small, human-authored manifest. Resolution is locked at
`plan` time into artifacts next to `matrix.jsonl`. Drift *refuses* — it does not
warn. Every result row carries enough provenance (dataset revision, recurve
commit, adapter version, oracle-env hash, seed) to be re-executed on its own.

Three things can change a number, and each has a citizen under the rule:

| Citizen | Intent (manifest) | Resolution (locked at plan) | Refuses on drift |
|---|---|---|---|
| **Dataset** | `[tasks]` benchmark + revision | local JSONL + content hash + count | `load_pinned` rejects a hash/count mismatch |
| **Model** | `[matrix]` models | frozen into `matrix.jsonl` before any run | cell ids derive from coordinates |
| **Oracle env** | `[oracle.env]` mode + image + digest | `oracle.lock.json` (digest present, platform, container Python, wrapper hash, resolved timeout, exclusion hash) | `plan` rejects a digest mismatch; a bare tag is refused outright |

The oracle was the last citizen to be naturalized: for a while it was a raw
`RECURVE_ORACLE_PYTHON` env var, whatever interpreter happened to be there, with
nothing recorded — two identical-looking rows could have been graded by different
oracles and nothing would show it. It is now pinned (image **digest**, not a
mutable `:tag`) and recorded (platform + emulation flag, because amd64-under-
Rosetta changes timing, and timing changes timeout verdicts).

## Why this matters here

Every harness defect in this design fails in *one direction*: a correct real
solution turned into an error, which reads as an oracle failure, which inflates
shipped-bad-work — the paper's own headline. A broken harness silently confirms
the thesis. That asymmetry is why the rule is strict (pin, refuse, record) and
why a **calibration gate** stands before any paid run: all 148 canonical
solutions are graded through the finished oracle path, keyed to the oracle-env
hash, and no paid cell runs while that pass rate is RED. Canonical solutions
cannot be wrong, so any bug in this class drops the rate and blocks the spend.

## Verbs

- `eval plan <manifest> --out <run>` — resolve the pinned matrix + `oracle.lock.json`; print the cost ceiling.
- `eval run <run>` — drive the matrix as a resumable, crash-resilient queue (refuses to spend without a passing calibration for the current oracle env).
- `eval analyze <run>` — `results.jsonl` → deterministic tables + honest figures, one pass.

Each verb has a file between it and the next (`matrix.jsonl` → `results.jsonl` →
`analysis/`), so every phase boundary is an inspectable, diffable artifact.

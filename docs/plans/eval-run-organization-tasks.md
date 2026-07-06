# eval run organization — task list

Execution checklist for `eval-run-organization.md` (the PRD is the source of
truth; this is just the ordered build order). The PRD's own §3–§5 hold the target
design, code sketches, and per-task acceptance criteria — each task points there.

Scope, per the PRD: this reorganizes the **run layout only** for `eval/src`
(`eval/src/cli.py::cmd_run`, the parallel `eval-architecture-epics` tree with
`core/`). It does not change how a cell runs, and does not touch the resumable
runner's crash-safety contract — it adds organization and audit *around* the
existing mechanism.

## Standing rules for every task

- **Plain comments only.** Comments and docstrings say what the code does, in
  plain language. **No** planning labels in code — no task ids (`RO1`, `RO3`), no
  section refs (`§3.6`), no `docs/plans/...` paths in docstrings. Those live here
  and in the PRD, never in a comment.
- **`git mv`, never delete+recreate**, for every migration move — history stays
  intact and any stale reference to an old path fails loud rather than silently
  pointing at wrong content.
- **Do not touch the runner's crash-safety contract** (per-cell fsync +
  seal-by-`cell_id` resume). This work only wraps it.
- **Keep the dogfooding gate green** (`.recurve/claims/eval`) through every task.

## Tasks

- task 1: add `core/run_id.py` and `core/run_paths.py` — a run's identity encoded as `<UTC-timestamp>-<short-git-sha>` (so "when, what code" is a directory listing) plus pure path computation for the co-located layout. Both are pure: the caller supplies `now`/`git_commit` at the boundary, so no real clock, git, or I/O lives inside. (detail: PRD §3.2, §3.5; acceptance §6 RO1)
- task 2: add `core/run_meta.py` and `core/run_index.py` — `run_meta.json` records the audit trail a run carries about itself (starting commit, adapter version, manifest hash, exact argv, and a growing list of continuations); `index.jsonl` records one line per run so an experiment's whole history is `cat`-able without opening a run dir. (detail: PRD §3.3, §3.4; acceptance §6 RO2)
- task 3: wire `cmd_run`'s three modes — default **fresh managed run** (auto-computes a new timestamped dir that never collides, writes `run_meta.json`, relinks `latest`, appends to `index.jsonl`); `--continue <run-id|latest>` (extends an existing run under the same experiment via the existing resume-by-`cell_id`, appending a continuation entry); and `--out <path>` (unchanged unmanaged escape hatch — no meta, no index, explicit opt-out). Cell execution logic is untouched; only where things land and what gets recorded about the landing changes. (detail: PRD §3.6; acceptance §6 RO3)
- task 4: add the continuation drift warning — continuing a run under a different `git_commit` OR `oracle_env_hash` than the run started at prints a specific, unmissable warning and still proceeds (advisory, never a hard block); continuing under the same commit and hash prints nothing extra. This is what keeps a silently-mixed-code or mixed-oracle run visible. (detail: PRD §3.6, §3.7; acceptance §6 RO4)
- task 5: migrate the 3 real experiments and their existing run dirs into the new layout — `experiments/<name>/experiment.toml` for the live config and `experiments/<name>/runs/<run-id>/...` for each run, via `git mv`; backfill each migrated run's `run_meta.json` from what's knowable (e.g. the per-row `recurve_commit` already in `results.jsonl`); relink `latest`; delete the now-empty top-level `eval/runs/`. Existing `results.jsonl` content must be byte-identical post-move. (detail: PRD §4; acceptance §6 RO5)
- task 6: update `.gitignore` for the new paths — ignore `experiments/*/runs/*/cells|workspaces|transcript*` (the large, reproducible artifacts) while committing the small evidence (`run_meta.json`, `index.jsonl`, `manifest.toml`, `matrix.jsonl`, `results.jsonl`, `analysis/`). (detail: PRD §5)
- task 7 (optional, deferrable): add an `eval run-history <name>` verb that pretty-prints `index.jsonl` as a table (run id, commit, cells added, status). Not required for the core problem. (detail: PRD §6 RO6)
- task final: review work against eval-run-organization.md — confirm every §3–§5 target is met (co-located experiment/runs layout; timestamped, git-versioned, collision-proof run ids; the `run_meta.json` + `index.jsonl` audit trail; the three `cmd_run` modes; the drift warning; a clean `git mv` migration with byte-identical results and preserved history), the runner's crash-safety contract is unchanged, no planning labels leaked into any code comment or docstring, and the dogfooding gate is green.

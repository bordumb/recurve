# PRD — Eval run organization: co-located, timestamped, versioned, resumable

> Scope: `eval/src`'s run layout only (`eval/src/cli.py::cmd_run`, built in
> the `eval-architecture-epics` branch). `evallib`'s own `cmd_run`/`cmd_plan`
> are read here only as the current, evidence-gathering baseline — not
> edited; `eval/src` is where this program's future runs land.
>
> This is a planning document. Nothing here is implemented yet — file
> structure and code below are the target design, for review before any of
> it is built.

## 1 · The four problems, restated precisely

1. **Config and run are disconnected.** `eval/experiments/sw6-smoke.toml`
   (the intent) and `eval/runs/sw6-smoke/` (the evidence) are siblings under
   two unrelated top-level directories. Nothing on disk shows they belong
   together except a human remembering the naming convention.
2. **No temporal aspect — reruns silently collide.** A run's directory name
   is whatever `--out` was typed as, with no timestamp and no uniqueness
   guarantee. Re-running the same manifest into the same `--out` doesn't
   fail loud; it merges into the existing `results.jsonl` via the runner's
   resume-by-`cell_id` logic. That's the right behavior for resuming a
   *crashed* run — it's the wrong behavior for "I want to see this
   experiment's history," because there is no history, only one
   perpetually-overwritten present.
3. **No code-version audit trail at the run level.** Every *row* already
   carries `recurve_commit` (`provenance["recurve_commit"]`, via
   `evallib.cli._git_head` / same in `eval/src/cli.py::cmd_run`) — that part
   is fine. But nothing at the *run* level says "this run was produced by
   commit X" without opening `results.jsonl` and reading a row. Worse: if
   you re-run the same manifest after changing code, the merge in problem 2
   means a run directory can silently contain rows from two different
   commits with no flag anywhere that this happened.
4. **No graceful incremental coverage.** If a benchmark has 200–500 tasks
   and you want to run 50 today, 100 more tomorrow, there's no first-class
   way to do that *as a deliberate, audited choice* — only the accident of
   picking the same `--out` twice and hoping resume does the right thing
   (it does, for the cells themselves — see §4 below — but nothing records
   that this happened, when, or under what code).

## 2 · Current state (evidence)

```
eval/experiments/
  o6-smoke.toml
  poc-bcb-hard.toml
  sw6-smoke.toml
eval/runs/
  o6/                 manifest.toml, matrix.jsonl, results.jsonl, cells/
  sw6-smoke/           results.jsonl, workspaces/   (NO manifest.toml —
                        this run was produced by a one-off script,
                        run_sw6_smoke.py, not eval/src's cmd_run at all)
```

`--out` is a required, freeform string in both `evallib/cli.py` and
`eval/src/cli.py` — the CLI does not compute it:

```python
# eval/src/cli.py, today
sr.add_argument("--out", required=True,
               help="run directory (manifest.toml/matrix.jsonl/results.jsonl land here)")
```

The one thing already working in this program's favor: `core/runner.py`'s
resume contract (`sealed_ids`, skip-if-already-sealed) means **growing a
task sample and re-running into the same directory already produces
exactly the right cells** — the missing piece is organization and audit
around that mechanism, not the mechanism itself (see §4).

## 3 · Target design

### 3.1 · Directory layout

```
eval/experiments/
  sw6-smoke/
    experiment.toml            # the manifest -- was sw6-smoke.toml, moved+renamed
    runs/
      20260706T032210Z-4498221/     # one directory per run: <UTC timestamp>-<short git sha>
        manifest.toml                # frozen copy, exactly as today
        matrix.jsonl
        results.jsonl
        analysis/
        run_meta.json                 # NEW -- see 3.3
      20260707T091500Z-7a2f9c1/       # a second, later, independent run
        ...
      latest -> 20260707T091500Z-7a2f9c1/   # symlink, always the most recent run
      index.jsonl                     # NEW -- one line per run, see 3.4
  poc-bcb-hard/
    experiment.toml
    runs/
      ...
```

`experiment.toml` (the live, human-edited config) and `manifest.toml`
(inside a run dir, a frozen point-in-time copy) are now two different
filenames on purpose — conflating them is exactly today's confusion.

### 3.2 · `core/run_id.py` — a run's identity is (when, what code)

```python
"""core/run_id.py — a run's own identity, encoded directly in its
directory name so "when was this, what code produced it" is a directory
listing, not an investigation. Pure: callers supply `now`/`git_commit` at
the boundary (real time, real git HEAD) so this stays trivially testable.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone

_RUN_ID_RE = re.compile(r"^(\d{8}T\d{6}Z)-([0-9a-f]{7,40})$")


@dataclass(frozen=True)
class RunId:
    timestamp: datetime   # tz-aware, UTC
    git_commit: str        # short (7+) or full sha

    def __str__(self) -> str:
        return f"{self.timestamp.strftime('%Y%m%dT%H%M%SZ')}-{self.git_commit[:7]}"


def new_run_id(now: datetime, git_commit: str) -> RunId:
    return RunId(timestamp=now.astimezone(timezone.utc), git_commit=git_commit)


def parse_run_id(name: str) -> RunId:
    """Raises ValueError on anything that isn't a run id -- e.g. "latest"
    (a symlink name, not a run id) or a legacy freeform --out name."""
    m = _RUN_ID_RE.match(name)
    if not m:
        raise ValueError(f"not a run id: {name!r}")
    ts = datetime.strptime(m.group(1), "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
    return RunId(timestamp=ts, git_commit=m.group(2))
```

### 3.3 · `core/run_meta.py` — the audit trail a run carries about itself

```python
"""core/run_meta.py — run_meta.json: which code produced this run, when,
and (if extended over time) every later continuation's own code version
and coverage delta. This is what answers problem 3 and half of problem 4.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path


@dataclass
class Continuation:
    at: str                    # ISO8601 UTC
    git_commit: str
    oracle_env_hash: str | None   # None if this benchmark has no single shared lock (SWE-bench)
    requested_sample_n: int | None
    cells_added: int


@dataclass
class RunMeta:
    run_id: str
    created_at: str             # ISO8601 UTC
    git_commit: str              # recurve HEAD when the run STARTED
    adapter_version: str
    manifest_hash: str           # content hash of the frozen manifest.toml
    command: list[str]           # argv, for exact reproduction
    continuations: list[Continuation] = field(default_factory=list)


def write(path: Path, meta: RunMeta) -> None:
    path.write_text(json.dumps(asdict(meta), indent=2, sort_keys=True) + "\n")


def read(path: Path) -> RunMeta:
    d = json.loads(path.read_text())
    d["continuations"] = [Continuation(**c) for c in d.get("continuations", [])]
    return RunMeta(**d)


def append_continuation(path: Path, cont: Continuation) -> RunMeta:
    meta = read(path)
    meta.continuations.append(cont)
    write(path, meta)
    return meta
```

### 3.4 · `core/run_index.py` — an experiment's whole history, `cat`-able

```python
"""core/run_index.py — experiments/<name>/runs/index.jsonl: one line per
run (fresh OR continued), so an experiment's whole history is readable
without opening any run directory.
"""

from __future__ import annotations

import json
from pathlib import Path


def append(index_path: Path, entry: dict) -> None:
    index_path.parent.mkdir(parents=True, exist_ok=True)
    with index_path.open("a") as fh:
        fh.write(json.dumps(entry, sort_keys=True) + "\n")


def read_all(index_path: Path) -> list[dict]:
    if not index_path.exists():
        return []
    return [json.loads(l) for l in index_path.read_text().splitlines() if l.strip()]
```

### 3.5 · `core/run_paths.py` — where everything lives, computed not typed

```python
"""core/run_paths.py — pure path computation for the layout in 3.1. No
side effects, no I/O -- every function here just computes a Path."""

from __future__ import annotations

from pathlib import Path


def experiment_dir(experiments_root: Path, name: str) -> Path:
    return experiments_root / name


def manifest_path(experiments_root: Path, name: str) -> Path:
    return experiment_dir(experiments_root, name) / "experiment.toml"


def runs_root(experiments_root: Path, name: str) -> Path:
    return experiment_dir(experiments_root, name) / "runs"


def run_dir(experiments_root: Path, name: str, run_id) -> Path:
    return runs_root(experiments_root, name) / str(run_id)


def latest_link(experiments_root: Path, name: str) -> Path:
    return runs_root(experiments_root, name) / "latest"


def index_path(experiments_root: Path, name: str) -> Path:
    return runs_root(experiments_root, name) / "index.jsonl"
```

### 3.6 · `cmd_run`'s three modes

`--out` today is one undifferentiated freeform path. It becomes three
distinct, explicit modes:

| Mode | Flag | Behavior |
|---|---|---|
| **Fresh managed run** (default) | *(neither flag given)* | Auto-computes `run_paths.run_dir(experiments_root, name, new_run_id(now, git_head))` — always new, never collides. Writes `run_meta.json`. Updates `latest` + appends to `index.jsonl`. |
| **Continue a managed run** | `--continue <run-id\|latest>` | Resolves to an existing run dir under the SAME experiment. Extends it (existing resume-by-`cell_id` logic does the real work). Appends a `Continuation` entry to `run_meta.json` — warns (not blocks) if `git_commit` or `oracle_env_hash` differs from the run's own start. |
| **Unmanaged / ad hoc** | `--out <path>` (unchanged) | Escape hatch for throwaway/dev use (e.g. a `--dry-run` smoke during development) — no `run_meta.json`, no index entry, no `latest` update. Explicit opt-out, never the default. |

```python
def cmd_run(args) -> int:
    manifest = _load_manifest(args.manifest)          # unchanged
    ...
    name = manifest["experiment"]["name"]
    git_commit = _git_head(REPO)                       # already exists, reused

    if args.out:
        run_dir = Path(args.out)                        # unmanaged escape hatch, unchanged behavior
        managed = False
    elif args.continue_run:
        run_dir = _resolve_continue_target(EXPERIMENTS_ROOT, name, args.continue_run)
        meta = run_meta.read(run_dir / "run_meta.json")
        if meta.git_commit != git_commit:
            print(f"warning: continuing a run started at {meta.git_commit}, "
                 f"current HEAD is {git_commit} -- cells added now are graded "
                 f"under different code than the ones already sealed", file=sys.stderr)
        managed = True
    else:
        rid = run_id.new_run_id(datetime.now(timezone.utc), git_commit)
        run_dir = run_paths.run_dir(EXPERIMENTS_ROOT, name, rid)
        run_dir.mkdir(parents=True)
        managed = True

    # ... existing plan / admits_spend / expand / materialize+agent / grade /
    # orchestrate / runner.run logic, entirely unchanged, using `run_dir` ...

    if managed:
        _record_run_completion(run_dir, name, git_commit, n_cells_added, ...)  # write/append run_meta,
                                                                                 # relink latest, append index
    return 0
```

Nothing about *how a cell runs* changes — this section is purely about
*where things land and what gets written about the landing*.

### 3.7 · Why problem 4 is mostly already solved (and what's actually missing)

`core/runner.py::run` already resumes by `cell_id` — a task's `task_id`
comes from the task dict itself, not its position in a list, so growing
`[tasks].sample.n` from 50 to 100 and re-running into the **same** run
directory produces the union: the first 50 cell ids are unchanged and
skipped (already sealed), the new 50 run fresh. **This already works
today** — the gap isn't resumability, it's that there's no ergonomic,
audited way to point at "the same run, again, later" (that's `--continue`,
§3.6) and no record of *when* each batch was added or *under what code*
(that's `Continuation`, §3.3).

The one real risk this surfaces, worth guarding explicitly: if the
**oracle environment** changes between two continuations (image rebuilt,
new digest) while the **dataset sample** merely grows, a run could
silently mix cells graded under two different oracles. `Continuation`
records `oracle_env_hash` per continuation precisely so this is visible,
and `_resolve_continue_target`'s warning (§3.6) should extend to checking
it, not just `git_commit`.

## 4 · Migration

One-time, mechanical, done by hand (small enough not to script) or a tiny
`migrate_runs.py`:

1. For each `experiments/<name>.toml`: `mkdir experiments/<name>` and `git
   mv experiments/<name>.toml experiments/<name>/experiment.toml`.
2. For each existing `runs/<name>/`: compute a legacy run id from its
   earliest file's mtime + `"legacy"` in place of a commit (e.g.
   `20260705T211500Z-legacy`) and `git mv runs/<name> experiments/<name>/runs/<that-id>`.
   Write a `run_meta.json` for it with whatever's actually knowable
   (`git_commit: "unknown"` where a run predates per-row provenance, e.g.
   `sw6-smoke`'s own results already carry `recurve_commit` per row — that
   value can backfill `run_meta.json.git_commit` directly).
3. Relink `latest` for each migrated experiment.
4. Delete the now-empty top-level `eval/runs/`.

## 5 · `.gitignore` updates

```diff
- runs/*/cells/
- runs/*/workspaces/
- runs/*/**/transcript*
+ experiments/*/runs/*/cells/
+ experiments/*/runs/*/workspaces/
+ experiments/*/runs/*/**/transcript*
```

`run_meta.json`/`index.jsonl` are small and committed, same rule already
applied to `manifest.toml`/`matrix.jsonl`/`results.jsonl`/`analysis/`.

## 6 · Tasks

- [ ] **RO1 — `core/run_id.py`, `core/run_paths.py`.** Pure, hermetically
  tested (no real clock/git needed — both take their inputs). *Acceptance:*
  round-trip `new_run_id` → `str` → `parse_run_id`; every `run_paths.*`
  function checked against the layout in §3.1.
- [ ] **RO2 — `core/run_meta.py`, `core/run_index.py`.** *Acceptance:*
  write → read round-trip preserves every field including
  `continuations`; `append_continuation` is additive (never drops a prior
  entry); `run_index.append`/`read_all` round-trip.
- [ ] **RO3 — Wire the three `cmd_run` modes (§3.6).** *Acceptance:* no
  flags → new timestamped dir every invocation, never collides with a
  prior one; `--continue latest` extends the most recent run and appends
  a `Continuation`; `--out` behaves exactly as it does today (regression,
  not a new behavior).
- [ ] **RO4 — The code-version / oracle-env continuation warning.**
  *Acceptance:* continuing at a different `git_commit` or
  `oracle_env_hash` than the run started at prints a clear, specific
  warning and still proceeds (never silently blocks); continuing at the
  SAME commit/hash prints nothing extra.
- [ ] **RO5 — Migrate the 3 real experiments + their existing run dirs**
  (§4). *Acceptance:* `git log --follow` still tracks each moved file;
  `poc-bcb-hard`/`sw6-smoke`/`o6-smoke`'s existing `results.jsonl` content
  is byte-identical post-move.
- [ ] **RO6 (nice-to-have) — `eval run-history <name>` verb.** Pretty-
  prints `index.jsonl` as a table (run id, commit, cells added, status).
  Not required for the core problem, easy to defer.

## 7 · Risks & non-goals

- **Not** solving multi-machine/multi-worker sharding (`eval-docs`'s own
  G4, already deferred there) — this is single-machine organization only.
- **Not** changing the resumable-runner's own crash-safety contract
  (`core/runner.py`'s per-cell fsync + sealed-id skip) — this plan only
  adds organization and audit *around* it.
- **Migration touches real, already-referenced evidence
  (`sw6-smoke`'s results, cited in commit messages and
  `docs/research/`-style write-ups already committed this session).**
  Use `git mv`, never delete+recreate, so history and any existing
  external references to the OLD path fail loud (file not found) rather
  than silently pointing at stale content.
- **`--continue`'s warning is advisory, not a hard gate.** A user who
  knows exactly why the commit changed (e.g. a pure refactor with no
  behavior change) should be able to proceed without friction — this
  mirrors this program's own existing posture (`admits_spend` blocks;
  code-version drift only warns, since it is not always wrong to mix).

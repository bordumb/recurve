# Epic B — One CLI for N benchmarks

**Leverage:** high (makes the second benchmark actually runnable).
**Depends on:** Epic A (needs the `Benchmark` registry). Do A1–A4 first.

---

## So what? (plain English)

There are two benchmarks in the tree, but the command-line tool can only drive
one. `eval plan` / `eval run` / `eval calibrate` are wired to BigCodeBench and
nothing else. SWE-bench can only be exercised from Python/tests — there is no
`eval` command that runs it, even though the code's own error messages tell users
to run `eval swebench plan` and `eval swebench build`, **which don't exist.** So a
user following the remediation instructions hits a dead end. Adding a third
benchmark today means editing the CLI's hardcoded fetch/calibration paths a third
time. The CLI should look up *which* benchmark from the manifest and dispatch,
the way the rest of the kernel already dispatches on port names.

## Current state (evidence)

**Task resolution ignores the declared benchmark** and hardcodes BigCodeBench:

```python
# evallib/cli.py:22-30
def _resolve_tasks(manifest, cache_dir):
    from evallib.taskstore import load_pinned, fetch_bigcodebench_hard   # ← BCB only
    t = manifest["tasks"]
    if t.get("local"):
        return load_pinned(t["local"], t.get("hash"), t.get("count"))
    return fetch_bigcodebench_hard(t["revision"], cache_dir)             # ← t["benchmark"] never read
```

**Calibration hardcodes BigCodeBench file names and the grading call:**

```python
# evallib/cli.py:240 (cmd_calibrate)
cal_file = repo / "eval" / "datasets" / f"bcb-hard-calibration@{revision}.jsonl"  # ← "bcb-hard-" literal
...
# evallib/cli.py:258 — grades via quarantine.oracle_verdict (BCB grading), not a benchmark method
```

**No SWE-bench verbs exist.** `cli.py`'s argparse defines `plan`, `run`,
`analyze`, `calibrate`, `oracle build` — none benchmark-aware
(`cli.py:294-312`). Yet:

```python
# evallib/swebench_env.py:112-119  — points users at commands that DON'T EXIST
"derive it from SWE-bench's own instance-building tooling with
 `eval swebench build <instance_id>` … then re-run `eval swebench plan`."
```

**The oracle-env resolution is single-shape.** `cmd_plan` calls `build_lock` and
writes one `oracle.lock.json` (`cli.py:50-66`); SWE-bench's per-instance locks
(`experiments/sw6-smoke.toml:46-51`, `per_instance = true`) have no path through
this verb at all.

## Target design

The three verbs resolve the benchmark once, from `manifest[tasks].benchmark`, and
call descriptor methods. The CLI stops knowing any benchmark's name.

```python
# cli.py  (target)
def _benchmark(manifest):
    from evallib.benchmarks import resolve            # Epic A registry
    return resolve(manifest["tasks"]["benchmark"])    # KeyError-with-known-names if absent/unknown

def _resolve_tasks(manifest, cache_dir):
    return _benchmark(manifest).load_tasks(manifest, cache_dir)   # seam 1

def cmd_plan(args):
    bench = _benchmark(manifest)
    ... bench.resolve_oracle_env(manifest) ...        # shared-digest OR per-instance, polymorphic
def cmd_calibrate(args):
    bench = _benchmark(manifest)
    ... bench.calibrate(manifest, repo) ...           # seam 5; no "bcb-hard-" literal
```

`per_instance` oracle envs write a `oracle.locks.json` (plural) via the SWE
descriptor's `resolve_oracle_env`; the shared-digest case writes today's
`oracle.lock.json`. The spend gate (`assert_spend_admitted`, `cli.py:93`) asks the
descriptor where its calibration lives instead of computing the path itself.

## Tasks

- [ ] **B1 — Route `_resolve_tasks` through the registry.** Replace the hardcoded
  `fetch_bigcodebench_hard` with `_benchmark(manifest).load_tasks(...)`.
  *Acceptance:* BigCodeBench manifests behave identically; a manifest naming an
  unknown benchmark fails loud at plan time with the known-names list.

- [ ] **B2 — Make oracle-env resolution polymorphic.** `cmd_plan` delegates to
  `bench.resolve_oracle_env(manifest)`, which returns either a single lock
  (BCB) or a per-instance lock set (SWE). Write `oracle.lock.json` or
  `oracle.locks.json` accordingly. *Acceptance:* `eval plan` on
  `experiments/sw6-smoke.toml` produces per-instance locks; on `poc-bcb-hard.toml`
  produces today's single lock byte-for-byte.

- [ ] **B3 — Make calibration a benchmark method.** Move the `bcb-hard-calibration@`
  path + `quarantine.oracle_verdict` grading out of `cmd_calibrate` into
  `benchmarks/bigcodebench.py::calibrate`; add `benchmarks/swebench.py::calibrate`
  (per-instance, canonical `patch` applied — the logic already in
  `swebench_calibration.run_canonical_patch_calibration`). *Acceptance:*
  `eval calibrate` works for both; no benchmark literal remains in `cli.py`.

- [ ] **B4 — Add the missing build verb.** Implement `eval build <instance_id>`
  (or a benchmark-agnostic `eval oracle build`) that, for SWE-bench, calls
  `swebench_env.build_environment_image`; for BCB, the existing derived-image
  build. Wire it so the remediation messages in `swebench_env.py:112` and
  `oracle_build.py` point at commands that **actually exist**. *Acceptance:* the
  message a fresh clone sees names a runnable command.

- [ ] **B5 — Unify the run path.** `cmd_run` builds the adapter from the descriptor
  (`bench.grade`, `bench.workspace_port`) rather than importing
  `make_pipeline_adapter` directly, so one `eval run <dir>` drives any benchmark.
  *Acceptance:* `eval run` on a SWE-bench run dir executes through the shared
  runner + shared orchestrator (Epic A) with SWE grading.

- [ ] **B6 — Delete or redirect the dead `eval swebench …` references.** Every
  string that names a CLI command must resolve to a real subparser. *Acceptance:*
  `grep -rn "eval swebench" evallib/` returns only real, wired commands.

## Risks & constraints

- **Do not weaken the spend gate.** B2/B3 must keep "no paid cell without a
  passing calibration for THIS oracle env" true for both shapes. The per-instance
  case needs the gate to check *every* instance's calibration, not just one.
- **Frozen manifests must stay legible.** `cmd_plan` freezes `manifest.toml` into
  the run dir (`cli.py:40`). Old runs (e.g. `runs/o6/`) predate the registry;
  don't retroactively break their replay. A missing `benchmark` key should default
  to `bigcodebench-hard` for backward compatibility, with a deprecation note.
- **Keep the phase-boundary-as-file rule.** Each verb still writes exactly one
  artifact the next reads (`eval/README.md:46-52`). Per-instance locks are a new
  artifact, not a change to that rule.

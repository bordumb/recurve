# eval — the recurve evaluation pipeline, gated

The instrument is held to the standard it measures. The `eval/` pipeline
(docs/plans/eval-poc.md §5) turns an experiment manifest into pinned cells, runs
them through the BYO-agent seam, quarantines a held-out oracle, and analyzes the
results deterministically. Each stage is a claim here.

Design: the pipeline's core logic is stdlib-only, so these probes are hermetic —
they drive the real `evallib` code against fixtures, never the network or a paid
run. The one genuinely external dependency (fetching the real BigCodeBench-Hard
revision from HuggingFace) is an `oracle_waiver`: the probe runs full-strength
where the dataset is reachable and SKIPs (visible, non-blocking debt) where it is
not.

## EV-1 — TaskStore pins the benchmark to a content hash

`taskstore.py` loads a task set and pins it to a deterministic SHA-256 over the
canonical task content; `verify_pin` rejects any dataset that does not match its
recorded pin, and a changed task changes the hash. The pinning logic is
stdlib-only (hermetic); the real BigCodeBench-Hard fetch from HuggingFace needs
the optional `datasets` dependency and is oracle-waived where it is absent.
Negative space (guarded by the trap): a `verify_pin` that accepts a tampered
dataset against its original pin.

## EV-2 — Materializer builds A0/A3 workspaces and quarantines the oracle

`arms.py` maps an arm name to its workspace spec (pure): A0 is the bare task
statement + empty `solution.py`; A3 is the same, `recurve init`-ed.
`materialize.py` builds the git-init'd tmpdir, writing only what the agent may
see — never the hidden `test` field — and `assert_quarantined` refuses any
workspace in which the hidden test text appears. Negative space (guarded by the
trap): a materializer that accepts a workspace containing the hidden oracle.

## EV-3 — Runner: pinned matrix + resumable work queue

`plan.expand` turns a manifest and a pinned task set into the full cross product
(task × arm × model × budget × seed) with cell IDs derived from coordinates,
written to `matrix.jsonl` before any agent runs. `runner.run` drives each cell
through a BYO-agent adapter and seals exactly one row per cell; the resume
invariant is load-bearing — a re-run over a completed matrix invokes the agent
zero times, so a long paid run is safe to stop and restart. The adapters
(`claude.py`, `telemetry.py`) and the three CLI verbs complete the surface; the
gated logic is driven by a mock adapter (no spend). Negative space (guarded by
the trap): a runner that re-invokes the agent on already-sealed cells.

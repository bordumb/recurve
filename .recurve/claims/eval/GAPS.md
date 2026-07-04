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

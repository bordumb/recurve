# RUN — the sculptor's entrypoint

You are an agent told to run the improvement loop for **{{PROJECT}}**. This
file is your entrypoint: it tells you your first action and your exact stop
condition.

Your job: run **exactly ONE sculpting cycle** — take the ledger from N red
gaps to N−k, and leave every {{LABEL}} green. Not two cycles. Not "as many as
fit." One, finished and proven, then stop and report.

The whole loop is safe to run because one command is ground truth you cannot
argue with: **`{{PROG}} matrix --gate`** exits non-zero on any regression,
broken probe, stale artifact, or a guard probe that blessed its own
counterexample. Anchor every claim to it. A gap is closed when its probe is
GREEN and the gate is green fleet-wide — never because you believe it is.

---

## PREFLIGHT — never start on a broken or stale baseline

```bash
{{PROG}} validate     # the ledger must be sound (probes present, traps present)
{{PROG}} matrix       # the baseline: note which gaps are RED and that GATE is OK
```

- Any `BROKEN`: a probe is missing its prerequisite — fix the harness first.
  Do not start a cycle on a broken baseline.
- Any `STALE`: a {{LABEL}}'s built artifacts predate the tree — those probes
  were NOT run because their verdict would be a lie. Run that {{LABEL}}'s
  rebuild command, then re-run. **This is the rule for the whole cycle:**
  every time you change `{{TREE}}`, rebuild before trusting any probe.

## TRIAGE — value first; the policy lives in code, not here

```bash
{{PROG}} next         # highest-value open gap; review-gated and parked listed separately
{{PROG}} cycle new <name> --gaps <ID>    # scaffold the cycle plan with a captured baseline
```

Rules:
- **Never sculpt a review-gated gap** (`security-tradeoff`): a green gate is
  necessary but NOT sufficient there. Those go through REVIEW.md, never
  through an unattended cycle.
- If the gap's `smallest_fix` says "spike first", this cycle produces a
  design in `plan.md`, not code. That is a complete cycle.

## MOVE — close it, or break it down

Look at the recommended gap. Make **one move**:

- **Move A — close it** (below, SCULPT): provable honestly, in `{{TREE}}`,
  this cycle.
- **Move B — break it down** (below, DECOMPOSE): it isn't provable this
  cycle. **Do not force it.** An overreaching proof or a weakened probe to
  make a too-big gap fit one cycle is exactly the dishonesty the quality
  constitution exists to prevent — decomposing instead is the honest move,
  not a lesser one.

## SCULPT — the smallest honest change (Move A)

Make the smallest change in `{{TREE}}` that turns the recommended gap's RED
line GREEN, under the quality constitution (`.recurve/quality.md`). Build,
lint, and tests must be clean. No suppressions.

**Rules you cannot break:**
- Never `git reset`, `git checkout`, or otherwise revert shared state.
- Never touch sacred paths (see `[target] sacred` in recurve.toml).
- No loop vocabulary in the tree: gap IDs, cycle names, and the word that
  names this tool must not appear in product code — the change must stand
  alone as a real feature.
- Problems you discover but cannot close this cycle become NEW draft entries
  with probe sketches — never TODO comments, never silent scope drops.
- ~3 honest attempts on the gap, then park it with what you tried
  (`{{PROG}} park <ID> --reason ... --attempt ... --observed ...`) and stop.
  Parked is not abandoned: the gap stays open, your notes are the next
  cycle's head start, not a verdict that it can't be done.

## DECOMPOSE — RED-first break-down (Move B)

Cut the recommended gap into the smaller pieces it genuinely needs, and
mechanically check the cut is *sufficient* before spending effort proving
any of them (`docs/plans/autonomous_solver.md` §1 — sufficiency vs. taste):

1. Split it into the smaller claims it genuinely needs.
2. Write the **assembly**: a claim/lemma that derives the recommended gap's
   goal FROM those sub-claims taken as HYPOTHESES. Arm it RED-first (its own
   probe + trap) and gate it. **A GREEN here is a mechanical proof that
   "the sub-claims imply the goal"** — checked *before* you invest in
   proving any one of them. If it will not go GREEN, the breakdown itself
   is wrong — revise the cut, don't force the proof.
3. Arm every sub-claim RED-first (each its own probe + trap), and set
   `covers_claim: [<this gap's id>]` on every one of them (the assembly
   included — it is a child too). That is the DAG edge a later cycle — or
   `recurvelib.analysis.sufficiency` / `recurvelib.loop.solver`, recurve's
   own decomposition library, once wired to a CLI command in this project —
   walks to discharge this gap once every child closes.
4. `{{PROG}} baseline <suite>` arms the new entries for real. `{{PROG}}
   matrix --gate` must still hold: the assembly promotes to closed; the
   fresh sub-claims start open — RED is expected and correct for them.
5. **This gap itself stays OPEN.** It is discharged in a LATER cycle, once
   every child is closed and the assembly composes them into an
   unconditional proof (§PROMOTE covers that promotion) — not this one.

Report this cycle's status as `"decomposed"` (§REPORT), never `"closed"` —
the gap did not close; it was correctly, honestly cut down. That is still a
complete, successful cycle.

## REBUILD

Run the {{LABEL}}'s rebuild command. Probes read copied artifacts, not the
tree's build output — an un-rebuilt {{LABEL}} makes every verdict a lie.

## GATE — the conjunction, in order

```bash
{{PROG}} probe --gap <ID>     # the gap's own probe: GREEN
{{PROG}} matrix --gate        # fleet-wide: zero regressions/broken/stale/failed traps
```

Then the {{LABEL}}'s behavioral harness if it has one. All of it, every cycle.

**Fast gate (`--cache`).** `{{PROG}} matrix --gate --cache` is the *same* fleet-wide gate,
only faster: it skips any probe whose check file and the project sources it imports are
unchanged since that probe's last verdict, reusing the stored GREEN/RED. It is **sound** — a
probe whose inputs moved is always re-run, so it catches regressions exactly as the full gate
does — and the node you just sculpted always re-runs (its source changed). Use it for fast
iteration and the per-cycle gate. **Run the plain uncached `{{PROG}} matrix --gate` where the
verdict must be ground-truth fresh: before a PR/merge, before `{{PROG}} baseline`, before a
published report, and any time you doubt the built artifacts.** The cache is off by default —
nothing changes unless you pass `--cache` — and its store lives in `.recurve/cache/` (gitignore
it). It does **not** replace the rebuild: an un-rebuilt {{LABEL}} is still a lie; `--cache` only
skips re-*measuring* what provably cannot have changed, never re-*building*.

## PROMOTE

Edit the ledger entry `open → closed`. Rewrite its GAPS.md section to
describe the NEW reality (the gap becomes a feature note). Run
`{{PROG}} coverage --gate` — prose and ledger must not drift.

## SNAPSHOT + COMMIT

Write `cycles/<name>/outcome.md` (what changed, what the gate said) and the
diffs. Commit policy: **{{COMMIT_POLICY}}**.
{{COMMIT_NOTE}}

## REPORT — then STOP

Emit one structured run record (see `schema/run-record.schema.json`):
status `closed | decomposed | parked | no-work-left | failed`, the gap,
attempts, files touched, verdict deltas, one-paragraph summary. If
`$RECURVE_RESULT_FILE` is set you are inside the loop: write the record
THERE — the loop validates and appends it for you (append is idempotent, so
an extra `{{PROG}} record append --file <record.json>` is harmless).
Running standalone, append it yourself with that command. Then stop. One
cycle = one agent. The ledger is the only memory the next agent gets.

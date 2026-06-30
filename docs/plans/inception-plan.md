# recurve — a general toolkit for claims-driven recursive software improvement

> **One line:** point recurve at a target — an existing repo or a PRD — and it
> converts intent into falsifiable claims with executable probes, then burns
> down the gap between *claimed* and *proven*: one fresh agent per cycle,
> ratcheting monotonically, parking what it can't prove, and reserving for
> humans exactly the judgments machines shouldn't make.
>
> **Provenance:** generalized from two working instances — a demo-suite
> improvement loop (rictl: 5 demo suites, 49 gaps, two unattended burndown
> campaigns) and a protocol-conformance suite (ictl: federated onto the same
> schema with its own oracles). Every design rule in this plan was learned,
> not invented; the failure-mode catalog (§11) cites the actual incidents.
>
> **Provenance hygiene:** concrete paths into both ancestors live in the
> appendix — and only there. The origin platform's name and its domain
> technologies appear nowhere in this plan's normative text, and no
> provenance vocabulary (instance names, gap IDs, incident tags) may ship in
> `recurvelib`, the CLI, or anything `init` stamps — recurve must read as if
> it had no first customer. The self-hosted suite probes this (§14).

---

## 1. The thesis being generalized

The two instances prove a loop with these properties:

- **Claims are falsifiable or they don't exist.** Every promise has an
  executable probe with a RED/GREEN verdict. The ledger records *verified
  observations*, never intentions (drafts live in separate files until a
  baseline run promotes them).
- **The probe is the spec.** Agents never decide what "better" means; they
  turn one specific RED line GREEN without breaking ~50 guarded others.
- **The ratchet only turns one way.** Closed claims keep their probes as
  regression guards; a fleet-wide gate (`matrix --gate`) makes silently
  undoing prior work impossible.
- **Fresh agent per cycle; the ledger is the only memory.** No context rot,
  contained failures, and a per-cycle snapshot/commit trail for rollback.
- **The system knows its blind spots.** A `security-tradeoff` class exists
  because a green gate cannot prove a *loosened check* is safe — those route
  to an adversarial human/independent-reviewer protocol instead of the loop.
- **Improvement pressure comes from consumers.** Demos/specs make claims; the
  platform gets hardened against the claims its own use cases make.

recurve's job is to make this shape **installable in an afternoon** against
any repo or spec, instead of hand-built per project.

### The bet (why this is more than tooling)

If this shape installs anywhere, the unit of software work stops being the
PR and becomes the **claim**. Humans own three artifacts — the claims, the
constitution, and the adjudications — and review *those*; agents own
everything between a RED probe and a green gate; diff review becomes a
sampling activity, not a bottleneck. The artifact that ships is not "code
that passed CI" but **code accompanied by its evidence**: a ledger of
falsifiable claims, each with a probe anyone can re-run. recurve is the
smallest tool that makes that inversion installable — every section below
is in service of keeping the evidence honest while removing the human from
everywhere except judgment.

### What varied between the two instances (→ configuration)

| Concern | recursive_improvement | interop | recurve answer |
| --- | --- | --- | --- |
| Sculpted tree | a sibling platform tree | the *same* sibling tree (shared!) | `[target] tree` in config; federated gate when shared |
| Ledger discovery | glob `*/gaps.yaml` across demos | single pinned file | explicit suite list in config (no globs — see §11.16) |
| Verdict oracle | demo harnesses (smoke.sh, run.sh) | pinned third-party peer implementations (exact versions) | per-suite harness dir + `versions.lock` convention |
| Rebuild step | per-demo `scripts/build.sh` | suite `scripts/build.sh` (shim) | per-suite `rebuild` command in config |
| Freshness | content-hash bin vs platform; mtime for ffi/web | one platform binary only | declarative artifact→source map in config |
| ctl | `rictl` (full) | `ictl` (thin wrapper over riclib) | one `recurve` CLI; suites are config, not forks |
| Commit policy | none → unsigned-per-cycle (evolved) | n/a | explicit policy in config (§11.1) |

### What never varied (→ the core, frozen)

The gap schema, probe exit-code contract, status semantics
(open→RED / closed→GREEN / permanent→no probe), the prose↔ledger coverage
discipline, the cycle procedure shape (triage → sculpt → rebuild → gate →
promote → snapshot), value-first triage, the review-gated class, parking,
and the watchdogs. These are the product. Do not make them configurable.

---

## 2. Vocabulary (one term, one meaning, everywhere)

- **Claim** — a falsifiable statement about the target ("revocation propagates
  in <1s p99"). Exists as prose (GAPS.md section) + ledger entry + probe.
- **Gap** — a claim whose probe is RED: the delta between claimed and proven.
  A *closed* gap is a claim whose probe is GREEN and guarded forever.
- **Probe** — an executable that emits GREEN (exit 0), RED (exit 1), or
  BROKEN (exit 2, missing prerequisite — *not a verdict*).
- **Trap** — a kept counterexample fixture that MUST turn its probe RED
  (interop's tampered-twin pattern, generalized). A probe that has never
  been seen RED is not yet evidence (§8.8).
- **Suite** — one ledger + prose + probes + harness for one domain (a demo,
  a conformance target, a PRD's feature area).
- **Ledger** — `gaps.yaml`: the machine record of verified observations.
- **Draft** — `*.draft.yaml`: schema-shaped intentions awaiting the promotion
  ceremony (probe written → baseline run → observed output quoted → live).
- **Harness / oracle** — the fixtures and ground-truth implementations probes
  compare against (a peer implementation, a TLS stack, a live demo run).
- **Gate** — the conjunction that must be green to promote: probe GREEN +
  fleet matrix (no regression/broken/stale across ALL suites sharing the
  tree) + the suite's behavioral harness.
- **Cycle** — one fresh agent taking the ledger from N red to N−k, proven,
  snapshotted, committed (per policy), reported.
- **Park** — marking a gap un-greenable-this-run for human triage; the loop
  continues past it (never halts on it).
- **Review-gated** — `security-tradeoff` class: green gate necessary but not
  sufficient; requires the adversarial protocol (§12).
- **Freshness** — whether built artifacts a probe reads are current with the
  sculpted tree; STALE blocks the probe from running (a stale verdict is a lie).
- **Coverage** — the prose↔ledger link check: every documented claim has a
  ledger entry (orphans are invisible to the loop and therefore never fixed).

---

## 3. Toolkit shape

Three deliverables, in dependency order:

1. **`recurvelib`** — the engine, extracted from `riclib` (model, probe
   runner, matrix, freshness, coverage, triage, cycle scaffolds). `riclib`
   is already 90% of this; `ictl` proved it wraps cleanly. Python, stdlib +
   PyYAML only (both instances survive on this; zero install friction).
2. **`recurve` CLI** — `rictl`'s surface, project-configured:

   ```
   recurve init [--from-prd <file>] [--from-repo]   # scaffold (§7)
   recurve ledger | show <id> | validate            # read the ledger
   recurve next                                     # value-first triage
   recurve probe [--suite S | --gap ID]             # run probes
   recurve matrix [--gate]                          # federated conformance gate
   recurve freshness [--gate]                       # artifact currency
   recurve coverage [--gate]                        # prose↔ledger link
   recurve cycle new <name> --gaps ID,ID            # scaffold a cycle plan
   recurve review <id>                              # adversarial-review brief
   recurve adjudicate <id>                          # record a policy fork / amend or retire a claim (§12.3, §6)
   recurve import <suite>                           # seed drafts from prose
   recurve baseline <suite>                         # the promotion ceremony (§6)
   recurve park <id> --reason "..."                 # park / list parked
   recurve drill [--suite S]                        # sabotage audit on a scratch tree (§14.2)
   ```

   Exit codes follow the house convention: 0 ok · 1 gate/validation failure ·
   2 usage/parse error. `--gate` flags are CI-grade (machine-meaningful exit).
3. **Templates** — what `recurve init` stamps into a target (§4, §10, §13).

### Target repo layout after `recurve init`

CONTAINED (decided post-Phase-4): the loop's entire footprint lives in one
dotdir so the target's root stays the product's own domain — the layout-level
form of §11.14's "workflow vocabulary must not leak into the product." The
only root touches are `.gitignore` (one state entry) and `.claude/` (skills).

```
<target>/
  .gitignore                   # gains: .recurve/state/
  .claude/skills/              # launcher / single-cycle / review skills
  .recurve/
    recurve.toml               # all variability lives here (§5); config
                               #   discovery checks <dir>/recurve.toml then
                               #   <dir>/.recurve/recurve.toml walking up;
                               #   paths resolve against the REPO root
    RUN.md                     # single-cycle agent entrypoint (template, §13)
    RUN-AUTO.md                # unattended-mode addendum
    REVIEW.md                  # the adversarial protocol
    TROUBLESHOOTING.md         # §11, symptom-first
    quality.md                 # the constitution preset (§9)
    claims/
      <suite>/
        GAPS.md                # the prose: one section per claim, stable anchors
        gaps.yaml              # the live ledger (verified observations only)
        gaps.draft.yaml        # intentions awaiting baseline (optional)
        probes/                # executables, 0/1/2 contract;
                               #   <name>.sh + <name>.trap/ fixtures (§8.8)
        harness/               # env.sh, oracles, fixtures, versions.lock
        cycles/                # per-cycle snapshots: plan.md, outcome.md, *.diff
    workflows/
      burndown.sh / .js        # the deterministic orchestrators (template, §10)
      burndown-parallel.sh     # the v2 lanes contract (§15.9)
    state/                     # gitignored run state: parked, records, receipts
```

Root layouts (recurve.toml at the repo root) remain fully supported — the
toolkit's own self-host suite uses one.

The schema ships in `recurvelib` (versioned), not copied per-target — the
instances proved the schema is the stable core; forks of it are drift.

---

## 4. The gap schema (inherited, minimally generalized)

Start from the ancestor gap schema (appendix: *Schema*) verbatim. It
survived two domains unchanged; resist improving it. Two generalizations only:

1. **`reads`** (the freshness axis) becomes an open string that must match a
   key in `[freshness]` config (§5), instead of the hardcoded
   `cli|ffi|web|state|none` enum. The semantics stay: it names *which built
   artifact the probe reads*, so the runner can refuse to run probes against
   stale artifacts.
2. **`class` stays the closed six** (`missing-surface`, `broken-route`,
   `wire-mismatch`, `security-tradeoff`, `staging`, `friction`). Both
   instances mapped cleanly onto them — interop mapped *conformance* onto
   them via a documented convention rather than new classes, and that's the
   precedent: new domains get a "Conventions" section in their GAPS.md, not
   new enum values. `security-tradeoff`'s review-gating semantics are
   load-bearing and must never be diluted by class proliferation.

Field discipline carried over unchanged: `observed` quotes *actual dated
output*; `evidence` pins `file:line`; `smallest_fix` is the minimal honest
change (and records adjudicated policy decisions — see §12.3); `unlocks` is
the sculptor's compass; `covers` anchors the prose link; probes are REQUIRED
unless `permanent`.

---

## 5. Configuration — `recurve.toml`

Everything that varied between the two instances, and nothing that didn't:

```toml
[project]
name = "myproject"

[target]
tree = "../platform"            # the tree cycles sculpt (may be ".")
sacred = ["~/.myapp", "/etc"]   # paths/resources no cycle may touch (§11.15)
forbidden_strings = ["GAP-", "recurve", "cycle"]  # must not appear in tree code (§11.14)

[commit]                        # §11.1–11.2 — the hardest-won section
policy = "unsigned-per-cycle"   # none | unsigned-per-cycle | signed
hooks = "run"                   # run | gate-supersedes (allows --no-verify IFF
                                #   [gate] provably covers the hook checks)
[gate]
# Conjunction, in order. {suite} expands per affected suite.
commands = [
  "recurve probe --gap {gap}",
  "recurve matrix --gate",
  "{suite}/scripts/smoke.sh",
]
quality = "default"             # the constitution (§9): default | <path to custom>

[suites.demo-alpha]
rebuild = "demo-alpha/scripts/build.sh"
harness = ["demo-alpha/scripts/smoke.sh", "DEMO_AUTO=1 demo-alpha/run.sh"]

[suites.conformance]
rebuild = "claims/conformance/scripts/build.sh"
harness = []                    # probe-only suites are legal (interop precedent)

[freshness]
# artifact the probes read        → source of truth it must be current with
"demo-alpha/bin/app"             = { source = "../platform/target/release/app", method = "content-hash" }
"demo-alpha/vendor"              = { source = "../platform/crates/app-ffi",     method = "mtime" }

[triage]
severity_order = ["headline", "feature", "friction", "cosmetic"]

[burndown]                      # knob defaults for workflows/burndown.js
cap = 12
max_consecutive_failures = 3
runaway_net_positive_cycles = 2
```

Rule: **if a knob didn't vary between the two instances, it doesn't go in the
config.** Config surface is where generalized tools go to die.

---

## 6. Claims: organization & lifecycle

### Organization

- **One suite per domain** with its own ID prefix (`LTL-`, `IOP-`, `PQ-`…),
  prose file, probes, and harness. Split suites when *harnesses* diverge, not
  when topics do (the aspirational-claims drafts keep 7 domains in one file
  because they share nothing *yet*; they split as harnesses materialize).
- **Prose first-class:** every ledger entry's `covers` anchors a GAPS.md
  section; `recurve coverage --gate` fails on orphans in either direction.
  The prose is for humans deciding; the ledger is for the loop executing;
  they must never drift (this is checked, not hoped).
- **Cross-suite claims are referenced, never duplicated** (the ancestor
  draft ledger's do-not-duplicate table pattern — appendix: *Draft
  discipline*). One claim, one owner-suite.

### Lifecycle (the promotion ceremony — `recurve baseline`)

```
draft entry (gaps.draft.yaml)         intentions; UNBASELINED observed; crate-level evidence
  → probe written                     accept path + adversarial path, 0/1/2 contract
  → `recurve baseline <suite>`        runs the probe for real
      RED  → promote to gaps.yaml as `open`   (observed = actual quoted output, dated;
                                               evidence pinned to file:line)
      GREEN → promote as `closed`             (a free win — file it; probe = guard —
                                               but only once seen RED on a trap, §8.8)
      BROKEN → fix the harness first          (a broken baseline blocks all cycles)
  → entry deleted from the draft file
```

This ceremony is the epistemological boundary of the whole system: the ledger
stays a record of *measurements*. An unattended agent must be able to trust
that every RED line in `gaps.yaml` is a real, reproducible observation — not
someone's prediction (the ancestor draft-ledger README argues the long form —
appendix: *Draft discipline*).

### Amendment & retirement (claims are not immortal)

Requirements change; a closed claim can become *wrong* without its probe ever
turning RED. The fix is never a quiet edit: `recurve adjudicate <id>` is also
the amendment ceremony — the same three-place synchronized change (§12.3)
re-baselines the claim, and a *retired* claim leaves a tombstone in the prose
("Retired <date>: superseded by X") with its probe deleted in the same commit.
A ledger that silently rewrites its past is no longer a record of
observations, and an agent that finds a guard probe contradicting current
prose must park, not pick a side.

---

## 7. Bootstrap modes — where claims come from

### A. Existing repo (`recurve init --from-repo`) — archaeology mode

An agent pass that mines *already-made promises*:
README feature claims, doc guarantees, error-handling contracts, test names
asserting behavior, CLI `--help` text. Each becomes a draft entry with a probe
sketch. Then baseline: many come up GREEN (file as closed guards — you've just
built a regression suite for your documentation), the REDs are your honest
backlog of broken promises. **The pitch for this mode: it makes a repo's
documentation falsifiable.**

### B. PRD / design spec (`recurve init --from-prd <file>`) — claimify mode

An agent pass that decomposes the spec into draft claims, with hard rules:

- Every claim must name its **observable** ("user can X and sees Y"), not its
  implementation ("uses Postgres").
- Every claim gets an **adversarial twin** sketched ("...and a wrong Z is
  rejected with a distinct error") — specs chronically omit the negative
  space, and the negative space is where products fail.
- **Ambiguities become questions, not guesses.** The claimify pass emits an
  `ADJUDICATE.md` of policy forks for the human (the IOP-L1d lesson, §12.3:
  one human sentence, then the decision gets *encoded into the probe* so all
  future agents are bound by it).
- Severity mapping: PRD "must" → headline/feature; "should" → friction;
  "could" → cosmetic. Anything the PRD calls security-relevant starts as
  `security-tradeoff` until a human downgrades it (default-closed, the safe
  direction).

Greenfield twist: with no code, *every* baseline is RED or BROKEN. That's
correct — the burndown *is* the build. BROKEN-at-baseline gets a bootstrap
ordering: the first cycles' gaps are "the harness exists," "the skeleton
builds," "probe X can run at all" — recurve should generate these
scaffolding gaps explicitly rather than letting cycle 1 face a wall of BROKEN.

Both modes end the same way: drafts → human skim of `ADJUDICATE.md` →
`recurve baseline` → a live ledger → burndown.

---

## 8. The probe contract (frozen; enforce, don't document-and-hope)

1. **Exit codes:** GREEN 0 · RED 1 · BROKEN 2 — and the map is **total**: any
   other exit (crash, signal, 127, the runner's timeout 124) coerces to
   BROKEN, never to a verdict. riclib already does this
   (`{0: GREEN, 1: RED}.get(rc, BROKEN)`); freeze it as spec, because a
   reimplementation that lets a segfault read as RED has invented a fourth
   state. The runner enforces a per-probe timeout — probes never get to hang
   the loop. BROKEN is "I could not measure" (missing oracle, fixture,
   build) and *blocks the gate* — absence of evidence never reads as a
   verdict (the capture-probe lesson: an empty packet capture because
   tcpdump wasn't running is BROKEN, not GREEN).
2. **Behavioral, not grep.** A probe must execute the built artifact. Source
   greps (`reads: none`-style) are permitted only when the claim is *about*
   source (a forbidden-string check) — and `recurve validate` should warn on
   every one, because greps are how probes get gamed.
3. **Both directions.** Accept path *and* at least one adversarial path. A
   claim probed only on its happy path is not a claim (the conformance
   instance's closed entries all reject a tampered twin, because an
   implementation that accepts *everything* must never masquerade as
   conformant).
4. **One RED line of truth.** When RED, print *the* detail line a sculptor
   treats as the spec ("ours=X oracle=Y"). The quality of this line is the
   quality of the next cycle.
5. **Hermetic + pinned.** Oracles pinned by exact version in
   `harness/versions.lock` (both instances do); fixtures regenerable by a
   checked-in script; no network unless the claim is about network.
6. **Freshness-declared.** Every probe's `reads` names its artifact key so
   the runner can refuse to run it stale (§5 `[freshness]`).
7. **Perf probes** additionally: pinned-rig notes in output, warmup, N≥1000,
   p99 not mean, thresholds with hysteresis (a flapping gate is a dead gate).
8. **A probe is not trusted until it has been seen to fail.** Every probe
   keeps at least one **trap** — a counterexample fixture it must turn RED —
   and `recurve baseline` runs traps before promoting anything: a
   GREEN-at-baseline claim with an unfalsified probe is indistinguishable
   from a probe that exits 0 unconditionally. Traps are mutation testing for
   the spec layer — they catch probe-weakening edits forever after, exactly
   as kept probes catch code regressions — and `matrix --gate` re-runs them:
   a trap going GREEN is a gate failure of the highest order. (This is §8.3
   made mechanical: the adversarial path stops being a convention an agent
   can skimp and becomes a checked artifact.)
   **Mechanism (decided):** traps are filesystem convention, not schema.
   `probes/<name>.sh` pairs with `probes/<name>.trap/` — one subdirectory
   per counterexample fixture; the runner re-invokes the probe once per
   trap with `TRAP_FIXTURE=<dir>` set and requires RED. No new schema field
   (§4 stays at two generalizations); `validate` fails a non-waived probe
   with no trap dir, and an empty trap dir reads as BROKEN, never as a pass.
   **Cost honesty:** traps are cheap where probes are fixture-driven (a
   tampered twin is a file swap) and genuinely hard elsewhere — a perf-SLO
   trap means a deliberately degraded build; a live-state behavioral trap
   may need a sabotaged scratch tree. Traps are therefore mandatory by
   default but **waivable per-probe**: a `trap_waiver: "<why>"` field in
   the ledger entry (legal — the schema admits additional properties),
   surfaced by `validate` as a counted, listed debt, so token traps and
   silent omissions are both visible. The sabotage drill (§14.2) is the
   partial repayment: it exercises end-to-end what waived traps skip
   per-probe.
9. **Deterministic, or declared.** Probes are deterministic by default; a
   claim that is inherently statistical declares a quorum in the probe
   itself (N runs, majority verdict). A probe observed flapping is
   quarantined as BROKEN — gate-blocking, never averaged into GREEN —
   because a flapping gate trains everyone to ignore the gate (§8.7's
   hysteresis rule, generalized beyond perf).

---

## 9. The cycle, generalized (RUN.md is the product)

The existing `RUN.md` is the single best artifact in either instance —
recurve templates it with config interpolation rather than rewriting it.
Shape preserved exactly:

```
PREFLIGHT   recurve validate && recurve matrix     # never start on a broken/stale baseline
TRIAGE      recurve next                           # value-first; review-gated listed separately
            recurve cycle new <name> --gaps …      # scaffold plan.md w/ captured baseline
SCULPT      smallest change in [target.tree] that turns the RED line GREEN,
            under the quality constitution (below); build/lint/tests clean;
            no suppressions
REBUILD     suite's rebuild command                # probes read copied artifacts, not target/
GATE        [gate.commands] in order — probe GREEN, federated matrix --gate,
            behavioral harness
PROMOTE     open → closed in gaps.yaml; rewrite the GAPS.md section to the
            new reality (the gap becomes a feature note)
SNAPSHOT    cycles/<name>/outcome.md + tree.diff + suites.diff
COMMIT      per [commit.policy]
REPORT      structured result; STOP (one cycle = one agent)
```

**The quality constitution** (the `[gate] quality = "default"` referent):
parse-don't-validate; ports/adapters at I/O edges; one source of truth;
delete divergent paths (no back-compat shims pre-launch); discovered
unrelated problems become NEW filed gaps with RED probes, never TODOs; no
fake green; bindings/consumers of a changed type are part of *your* change.
Projects may substitute their own constitution file; the default is the one
that produced cycle 1's "move the module down the dependency graph instead
of shimming" behavior — it earns its place.

**Spiked cycles:** design-heavy gaps (a recovery protocol, a new binding
design) get a plan/spike cycle first (the LTL-4 precedent — `cycles/<name>/plan.md`
exists for this). `recurve next` should flag gaps whose `smallest_fix`
self-declares "spike first."

---

## 10. Orchestration: yes, ship the workflow template

`workflows/burndown.js` is a **template with config injection** — the
ri-burndown script's third generation, with every evolution it earned:

- **Deterministic control flow in the script; judgment in the agents.** The
  loop, caps, parking, watchdogs, and halt conditions are code. The agent
  gets exactly one cycle and returns a schema-validated structured result
  (`status: closed | parked | no-work-left | failed`, gap, files, net_new_gaps,
  summary) — never free text the orchestrator has to interpret.
- **Knobs** (`args` > config defaults): `cap`, `suite` scope, `parked` seed
  list, `maxConsecFails`.
- **Park-and-continue** (gen 2 lesson): an un-greenable gap is parked with a
  reason and the loop moves on. Halt only on: no-work-left, cap, runaway
  scope (N consecutive net-gap-positive cycles), or M consecutive failures.
- **The cycle prompt embeds the hard rules** (no tree resets, no
  forbidden-string leakage, commit policy, sacred spaces, never sculpt
  review-gated gaps) — agents are stateless, so the prompt is the only place
  rules reliably reach them.
- **Parked gaps carry an attempt journal.** Parking writes *what was tried
  and why it failed* as structured data in the sidecar store (§15.8); when a
  parked gap is re-picked, the orchestrator injects prior attempts into that
  cycle's prompt. This is deliberately the only memory besides the ledger
  that crosses agents — bounded, gap-scoped, loaded only when relevant — so
  hard-won failure knowledge stops evaporating without reintroducing the
  context rot that fresh-agent-per-cycle exists to kill. Journal entries
  record **observations, never conclusions** — commands run, output seen,
  the RED line at stop — and the orchestrator frames them as "prior
  attempts, possibly mistaken: verify before trusting." A botched attempt
  written up as "X cannot work" must not anchor the next agent into never
  trying X properly.
- **Wrap-up agent** is read-only and reports: ledger delta, coverage, parked
  list with reasons, the review queue. The orchestrator's return value is a
  machine-readable run record.
- **The run record is a dataset, not a printout.** Every cycle emits one
  versioned, schema-validated record: gap, class, severity, attempts,
  wall-clock, tokens, files touched, verdict deltas, regressions caught at
  the gate. Define this schema in Phase 0 and never break it — every later
  ambition (close-rate priors feeding `recurve next`, cost prediction per
  class, comparing agent models on identical backlogs, dashboards) is a
  consumer of this one table. And name the by-product explicitly: each
  (tree snapshot, RED probe) pair is a *self-grading agentic task* — the
  gate is an oracle reward function. A mature recurve install accumulates a
  verifiable agent benchmark of its own domain for free, which is worth more
  than the tool.
- Companion **skill files** (the `/ri-burndown` pattern): a launcher skill
  for the burndown, a single-cycle skill (RUN.md driver), and a review skill
  (`recurve review` protocol driver). Skills are how humans invoke; workflows
  are how the loop executes; RUN.md is how a *lone* agent without the
  orchestrator behaves identically.

Orchestrator-portability note: burndown.js targets the Claude Code Workflow
runtime, but the contract it encodes (sequential fresh agents, structured
results, parking, watchdogs) must also be runnable as a dumb shell loop
(`while recurve next; do <spawn agent with RUN.md>; done`) so recurve isn't
married to one harness. RUN.md *is* that portability layer.

---

## 11. Failure-mode robustness (each entry: incident → rule)

This section is the toolkit's crown jewels; every rule was paid for.

1. **Interactive commit signing stalls the loop.** *(Incident: fn-10 run
   forbade commits entirely because gpg/SSH signing prompts hang headless
   agents; a later run evolved to unsigned per-cycle commits.)* → `[commit]
   policy` is explicit and detected at `init` (read `commit.gpgsign`); agents
   NEVER run a command that can prompt. `unsigned-per-cycle` is the
   recommended default: rollback granularity without signing ceremony; humans
   sign/squash later.
2. **Pre-commit hooks: slow, failing, or prompting.** *(Incident: a manual
   commit sat in multi-minute clippy+test hooks and was finally taken with
   `--no-verify` — safe only because the cycle gate had just run the same
   checks.)* → `hooks = "gate-supersedes"` permits `--no-verify` IFF the
   configured gate provably ran a superset of the hook checks that cycle;
   otherwise hooks run. Never globally; never to skip a failure.
3. **Un-greenable gaps must not halt the fleet.** *(Incident: gen-1 halted
   the whole run on one stuck gap.)* → park-and-continue with reasons; parked
   list is first-class output; `parked` seed knob lets the next run skip
   known stucks.
4. **Runaway scope.** *(Watchdog inherited from gen 1.)* → N consecutive
   cycles filing more gaps than they close → stop and report "re-scope."
5. **Repeated failure ≠ try harder forever.** → `max_consecutive_failures`
   halts; per-gap "~3 honest attempts then park/fail with what you tried."
6. **Agent death / API errors / harness restarts.** → structured results
   tolerate null (skipped agents); the orchestrator journal + resume
   (`resumeFromRunId` pattern) makes a killed run continuable with cached
   prefix results; per-cycle commits mean a dead run loses at most one
   cycle's work.
7. **Mid-run human stop leaves a half-written cycle.** *(Incident: a stop
   after cycle 7 caught cycle 8 mid-sculpt; recovery required surgically
   reverting 3 files — possible only because the per-cycle snapshot diffs
   identified non-overlap.)* → per-cycle commits (gen 2+) make this near-moot;
   snapshots remain the belt-and-suspenders; **agents never `git reset/
   checkout` shared state** (the gen-1 prompt rule, kept forever).
8. **Stale artifacts produce lying verdicts.** *(rictl's STALE machinery
   exists because probes read *copied* binaries, not `target/`.)* → freshness
   is declarative config; `matrix --gate` blocks on STALE; RUN.md says
   "rebuild proactively after every tree change."
9. **Broken ≠ red.** → BROKEN (exit 2) blocks the gate and the *baseline*;
   "do not start a cycle on a broken baseline" is a hard preflight rule.
10. **Probe gaming.** → behavioral requirement (§8.2), adversarial-path
    requirement (§8.3), traps making probe-weakening mechanically detectable
    (§8.8), `validate` warnings on grep probes, and the review-gated class
    for anything where green-while-wrong is plausible. The booby-trap
    precedent (LTL-3: the "obvious" fix re-opens a closed vulnerability and
    a naive probe would bless it) justifies the cost.
11. **Timeouts on long builds/tests.** → cycle prompts budget explicitly
    (the 10-minute cargo-nextest lesson); probes that need >T get a BROKEN
    "split me" failure rather than silent truncation; orchestrator treats a
    timed-out agent as a failed cycle (counts toward §11.5), not a hang.
12. **Machine sleep / environment loss.** → RUN-AUTO.md runbook: keep-awake
    (`caffeinate`), session-survival notes, and the resume procedure (§11.6).
13. **Concurrent loops on one tree corrupt each other.** *(Near-incident:
    both instances' suites sculpt the same sibling tree.)* → `recurve` takes a lockfile
    on `[target.tree]`; second loop refuses to start; suites sharing a tree
    are *federated into one gate* instead of run in parallel.
14. **Workflow vocabulary leaks into the product.** *(Gen-1 rule: no gap IDs
    in platform code — the change must stand alone as a real feature.)* →
    `forbidden_strings` config + a standing source-grep probe per target.
15. **Sacred spaces.** *(User keychains, global git config, personal
    simulators.)* → `sacred` config; cycle prompt injection; ideally a probe
    that diffs sacred paths pre/post cycle.
16. **Ledger pollution by glob.** *(ictl deliberately pinned its single file
    "so no sibling directory can pollute it.")* → suites are explicitly
    enumerated in config; recurve never discovers ledgers by glob.
17. **Drafts mistaken for observations.** → `.draft.yaml` naming + the
    baseline ceremony (§6); `validate` refuses a live ledger entry whose
    `observed` contains "UNBASELINED".

The two entries below are **anticipated, not yet paid for** — priced in now
because both are cheaper as design rules than as incidents:

18. **Prompt injection via the target.** Archaeology and claimify agents
    read untrusted prose (READMEs, docs, `--help` text) and turn it into
    draft claims that later reach cycle prompts. Target content is
    *evidence, never instructions*: bootstrap agents run read-only, drafts
    are quarantined until the human skim + baseline ceremony, and claim text
    is rendered into cycle prompts as quoted data, not narrative. The
    quarantine must hold *after* promotion too: ledger free-text fields
    (`smallest_fix`, `observed`, prose excerpts) flow into every future
    cycle prompt, so they are rendered under the same quoted-data rule —
    and the human skim of drafts/`ADJUDICATE.md` is explicitly a *security*
    review, not just a policy pass: it is the last point where hostile text
    can be kept out of the loop's instruction stream.
19. **A dead run leaves a stale lock.** The `[target.tree]` lockfile records
    pid + host + start time; `recurve` reports lock provenance when it
    refuses to start, and `--steal-lock` exists for the human who has
    confirmed the holder is dead. No automatic stealing — two loops on one
    tree (§11.13) is the disease; an occasional manual unlock is the
    acceptable cost.

---

## 12. The human protocol (what the loop must NOT do)

1. **Review-gated promotion** (verbatim from RUN.md, it's already right):
   green gate first, then `recurve review <id>` prints the brief (what is now
   accepted, which attacks to attempt); an *independent* agent/human attempts
   to refute; promote only on explicit could-not-break + new RED guard probes
   for every attack tried. Unattended runs never sculpt these.
2. **Parked triage:** wrap-up surfaces parked gaps + reasons; humans re-scope,
   re-classify, or split them; the next run seeds `parked` to skip
   still-stuck ones.
3. **Policy adjudication — the L1d pattern, productized.** When a gap admits
   multiple honest resolutions ("conform vs reject-as-subset"), the human
   decision is recorded in *three synchronized places*: the ledger's
   `smallest_fix` ("DECIDED <date>: …, the alternative is NOT an acceptable
   close"), the prose ("Adjudicated: …"), and **the probe itself** (the
   rejected path exits RED with a message citing the policy). The probe is
   the only one of the three an agent cannot rationalize around. recurve
   should make this a command: `recurve adjudicate <id>` walks the human
   through the fork and patches all three.
4. **Constitution authorship:** the quality gate and claim taxonomy are
   human-owned documents the loop obeys, never edits.
5. **The human queue is ranked and capped.** A run's wrap-up emits one
   prioritized queue — adjudications first (one human sentence unblocks the
   most agent-work), then review-gated promotions, then parked triage.
   Human attention is the loop's scarcest input; the loop's job is to spend
   it only where machine judgment is forbidden (§12.1–12.3), never on
   status. If the queue regularly exceeds what a human clears in ten
   minutes, that is a triage bug, not a human-diligence bug.

---

## 13. Documentation set (templates shipped by `init`)

| Doc | Audience | Source to generalize |
| --- | --- | --- |
| `RUN.md` | a lone agent running ONE cycle | the ancestor cycle entrypoint (appendix: *Cycle procedure*) — keep its voice: entrypoint, stop condition, "rules you cannot break" |
| `RUN-AUTO.md` | unattended operation | the ancestor unattended addendum (appendix: *Unattended runbook*) + §11.12 |
| `REVIEW.md` | the adversarial protocol | RUN.md §review-gated, expanded |
| `claims/<suite>/GAPS.md` | humans deciding | demo GAPS.md conventions + interop's class-mapping "Conventions" section |
| `ADJUDICATE.md` | bootstrap policy forks | new (§7.B) |
| `README.md` | first contact | the recipe style of the ancestor draft-ledger README (appendix: *Draft discipline*) |
| `TROUBLESHOOTING.md` | operators | §11, incident-first ("symptom → which rule fired → what to do") |

Documentation principle inherited from the instances: **every doc names its
reader and their next action in the first paragraph** (RUN.md: "This file is
your entrypoint… your first action and your exact stop condition").

---

## 14. Phasing & acceptance

- **Phase 0 — extract.** `recurvelib` out of `riclib` + `recurve.toml` +
  the CLI + the versioned run-record schema (§10) — defined now so data
  accumulates from the very first run. **Acceptance: re-host both existing
  instances on recurve with byte-identical ledger/matrix/coverage behavior**
  (rictl and ictl become thin aliases). The migration *is* the test suite —
  if recurve can't run its own ancestors, it generalized wrong.
- **Phase 1 — scaffold.** `recurve init` (blank + `--from-repo` archaeology),
  templates (RUN.md, burndown.js, skills), baseline ceremony, traps (§8.8),
  lockfile, parked store. Acceptance: a stranger repo goes from zero to a
  live ledger with 5 baselined claims and one completed cycle in under a
  day. **From Phase 1 exit, recurve hosts itself**: a `claims/` suite over
  the toolkit's own machine-probeable promises (byte-identical re-host,
  lockfile refusal, trap enforcement, BROKEN-coercion totality…), burned
  down by its own loop — a claims tool whose own claims aren't probed is a
  joke at its own expense, and self-hosting is the standing dogfood that
  catches generalization drift. Human wall-clock promises
  (init-under-a-day) stay here in the acceptance criteria, where humans
  verify them — an unprobeable claim in the self-host ledger would be
  exactly the aspirational prose the system forbids. Its first standing claim is **provenance hygiene**: a
  forbidden-strings probe (§11.14 turned on the toolkit itself) proving
  that no ancestor vocabulary or origin-domain technology appears in
  `recurvelib`, the CLI, or anything `init` stamps.
- **Phase 2 — unattended.** burndown.js template hardened with the §11
  catalog; resume; attempt journals; wrap-up records. Acceptance: an
  overnight run on a repo neither ancestor instance ever touched closes
  ≥3 gaps with zero human interventions and a clean parked/review report — **and passes a sabotage
  audit** (`recurve drill`): deliberately re-introduce one closed gap's
  defect on a scratch tree and the gate catches it (§8.8 applied to the
  whole install). The drill runs only on a scratch tree and leaves no trace
  in the ledger or run records — a drill that pollutes the dataset would
  poison the very evidence it exists to validate.
- **Phase 3 — claimify.** `--from-prd` + `ADJUDICATE.md` + `recurve
  adjudicate`. Acceptance: a greenfield PRD becomes a building, probed
  project where the burndown is the build. (Dogfood candidate: the ancestor
  aspirational-claims drafts — appendix: *Draft discipline* — promote them
  *through recurve*.)
- **Phase 4 — leverage.** Multi-target federation; dashboards over run
  records; **claim packs** — versioned, portable claim+probe+trap libraries
  for recurring claim shapes (CLI contract, REST conformance, perf SLO,
  no-phone-home, supply-chain) so a new project starts from a vetted pack,
  not a blank GAPS.md, and claims become a *distributable unit* the way
  packages are; **parallel burndown** — worktree-isolated cycles over
  disjoint suites with the federated gate as the serialization point
  (sequential stays the v1 contract until Phase 2 proves the gate; §15.9);
  **evidence receipts** — hash-chained verdict records (tree hash, probe
  hash, oracle versions from `versions.lock`, verdict, timestamp),
  optionally signed through a pluggable signer interface — recurve defines
  the receipt, never the signature scheme — so "code accompanied by its
  evidence" (§1) is checkable by someone who wasn't there. Receipts are the
  trust story for agent-built software: not "an agent wrote this," but
  "here is the re-runnable evidence, and here is the chain proving nobody
  edited it after the fact."

---

## 15. Open decisions (do not let an implementing agent guess)

1. **Name & home:** `recurve` as a standalone repo vs a tool dir inside the
   origin monorepo. (Standalone recommended at Phase 1 exit — §14.1's
   acceptance forces the clean dependency cut.) > Yes, standalone repo 
2. **Runtime:** Python (riclib heritage, zero-friction) vs Rust (house
   language of the first target). Recommendation: Python for the engine —
   the loop's value is conventions, not performance — but keep probes
   language-agnostic (they're just executables). > Yes, python
3. **Schema versioning:** how targets pin recurvelib's schema version, and
   the migration story when it (rarely) changes. > Yes, schema versioning
4. **Commit policy default** for `init`: `unsigned-per-cycle` recommended,
   but detect-and-ask beats silent default. > if in unsigned-mode, throw stern warning that they may want to sign after loop is done
5. **How opinionated is `quality = "default"`** — the constitution presumes
   pre-launch ("delete divergent paths, no back-compat"); mature repos need
   a softer preset. Two named presets (`pre-launch`, `stable`)? > Good idea
6. **Orchestrator coupling:** how much burndown.js assumes the Claude Code
   Workflow runtime vs the portable shell-loop fallback being co-equal (§10).
7. **Claimify model policy:** does `--from-prd` require human review of every
   draft (recommended) or only of `ADJUDICATE.md` forks? > Default to human review, with flag to turn off + message telling users about it 
8. **Parked store:** in-ledger field (`status: parked`?) vs sidecar state
   file. (Sidecar recommended — parking is *run* state, not claim truth;
   the schema's status enum is epistemics, not workflow.) The attempt
   journal (§10) lives wherever parking does.
9. **Parallel cycles:** strictly sequential is the v1 contract; when Phase 4
   adds worktree parallelism, what is the conflict rule when two cycles'
   tree diffs overlap? (Recommendation: the gate serializes — first to
   green wins; the loser's cycle is discarded and re-run fresh against the
   new baseline. Never merge two sculpts.)
10. **Evidence receipts format:** plain hash chain vs signed — and if
    signed, the shape of the pluggable signer interface. (Decide at Phase 4
    entry — but settle the receipt *fields* alongside the run-record schema
    in Phase 0, so early runs emit receipt-shaped records before anything
    signs them. The receipt format itself must stay free of any one
    project's signing technology.)

---

### Appendix: source map for the implementer

This table is the **only** place in the plan where concrete origin paths
appear, and it exists solely for the Phase 0 extractor. Nothing named here
may surface in `recurvelib`, the CLI, templates, or generated docs — the
provenance-hygiene probe (§14.1) holds that line.

| recurve concept | Lived implementation to read first |
| --- | --- |
| Engine | `auths-demos/recursive_improvement/riclib/` (model, coverage, cycle, freshness) |
| Schema | `recursive_improvement/schema/gap.schema.json` |
| CLI surface | `./rictl --help` and `interop/ictl --help` (the thin-wrapper proof) |
| Cycle procedure | `recursive_improvement/RUN.md` (+ `docs/recursive_improvement_workflows.md` §6) |
| Unattended runbook | `recursive_improvement/RUN-AUTO.md` |
| Orchestrator | the ri-burndown workflow script (gen 2: per-cycle commits, parking) + the `/ri-burndown` skill |
| Conformance federation | `interop/` (gaps.yaml header comment, harness/, peers/versions.lock, shim) |
| Draft discipline | `roadmap/aspirational_claims/{README.md, claims.draft.yaml}` |
| Adjudication pattern | `interop/gaps.yaml` IOP-L1d + `interop/GAPS.md` §L1d + `interop/probes/l1-said-icp-basic.sh` (the three-place DECIDED edit, 2026-06-12) |
| Trap discipline | interop probes' tampered-twin adversarial paths (every closed IOP entry rejects a mutated input) — §8.8 makes the pattern mandatory and checked |
| Incident history | §11 of this plan; the fn-10 branch log in both repos |

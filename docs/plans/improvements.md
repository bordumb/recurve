# PRD: recurve — target-type awareness + the multi-tree feedback loop

> **One line:** make `recurve` correct and low-friction on ANY target — a simple
> single repo, a non-Rust (web/node) project, or a **scaffold in one repo that
> hardens a platform in another** — by making it *target-type-aware* and
> *multi-tree-aware*, while keeping the single-repo case a one-command init.
>
> **Why now:** recurve was shaped for Rust-platform targets (the demos, interop,
> and the witness node all sculpt one `../auths` tree and read a compiled binary).
> Its first non-binary, cross-repo target (a Next.js frontend that also sculpts the
> backend) exposed the seams: a claimify that splits a spec by raw lines, a
> `forbidden_strings` default that doesn't match the claim ids it guards, a
> generated burndown workflow that throws under its own runtime, a binary-centric
> freshness model, and no first-class concept for "a scaffold that feeds a
> platform." Every one of those cost manual reconfiguring.
>
> **Build method:** recurve, dogfooded. This PRD is written to be *claimified*:
> every requirement names an observable and its adversarial twin, so recurve can
> burn down its own improvements and prove the new claimify on its own spec.
>
> **Status (landed June 2026):** **FR-E** (generated-workflow correctness), **FR-F**
> (`recurve install`), and **FR-C** (first-class `[target]` + `[sculpts.*]` multi-tree
> with a federated gate) are implemented and self-gated — see `claims/toolkit` **TK-15**
> (the stamped workflow carries no sandbox-forbidden call and resolves paths from an
> absolute root) and **TK-16** (the gate federates each sculpt's own gate command; its
> trap — a failing sculpt gate that still reports green — stays RED). FR-A/B/D/G/H remain
> open.
>
> **Compatibility:** the project is **pre-launch**, so backward compatibility is *not* a
> requirement — favor the clean design over matching prior bytes. A single-tree
> `recurve.toml` still validates and runs; the multi-tree model is opt-in and costs
> nothing until a `[sculpts.*]` is declared.

---

## 1. Introduction / Overview

recurve turns documented claims into probed, gated, burn-downable gaps. Today it
assumes one product tree, built into a compiled artifact, sculpted in place. That
assumption is invisible until the target breaks it. Three real shapes break it:

- **A non-binary target** (a web app). Freshness is `content-hash` over a built
  binary; a web bundle / source tree has no such artifact, so `reads` is left
  `none` and the gate can't tell stale from fresh.
- **A scaffold that hardens a platform.** A frontend that genuinely speaks to a
  backend *demands* capabilities the backend lacks; the honest fix is to sculpt the
  *other* repo. The demos had the identical shape. recurve has no config for it, so
  it lives in prose and per-cycle discipline.
- **A plain single repo** that just wants a clean init without hand-editing TOML.

This PRD makes the **target** a typed, possibly-multi-tree thing, fixes the
init/claimify/workflow defects that made the first non-Rust target painful, and
keeps the simple case simple.

## 2. Goals

- **G1 — Init that's ready, not a stub.** After `recurve init`, the config is fully
  wired for the target's kind; there is no "now hand-edit `recurve.toml`" step.
- **G2 — Target-type awareness.** `recurve` knows web vs rust vs node vs generic,
  and picks the right `reads` method, `rebuild`, `forbidden_strings`, and claimify
  class inference from the kind.
- **G3 — The multi-tree feedback loop is first-class.** A config declares a primary
  build target and zero-or-more *sculpt* targets in other repos; the loop builds
  the primary and sculpts the others when a claim demands it; the gate federates
  across all of them; commits land per-tree on per-tree branches.
- **G4 — Generated workflows run unmodified.** The burndown workflow `init` stamps
  runs as-is under its runtime: no forbidden runtime calls, no cwd assumption, no
  hardcoded binary path.
- **G5 — Claimify produces baseline-ready drafts.** Decomposition is by logical unit
  (bullet/requirement), titles are summarized not truncated, `smallest_fix` is a
  real first draft, and only genuine loosenings are review-gated.
- **G6 — An install story.** `recurve` gets onto PATH by a documented one-liner; the
  workflow never assumes a hand-made symlink.
- **G7 — Backward compatibility.** Every existing single-tree config and suite keeps
  validating and running with no edits.
- **G8 — Docs that match the tool.** Every new capability is documented with a
  worked example, the docs cannot drift from the shipped surface, and a newcomer
  learns recurve from its docs — not by reading its source.

## 3. User Stories

### US-1: Solo dev, single repo, one command
**As** a developer with one repo, **I want** `recurve init` to leave a config I can
`baseline` and run without editing TOML, **so that** the first loop is one command.

**Acceptance Criteria:**
- [ ] `recurve init --kind <k>` writes `tree`, `reads`, `rebuild`, and
      `forbidden_strings` already correct for kind `k`; `recurve validate` passes
- [ ] No placeholder in the emitted config says "edit me" for a required field
- [ ] Adversarial: an init that leaves a required field empty fails its own
      post-init self-check

### US-2: A scaffold that hardens a platform (cross-repo feedback loop)
**As** a developer building a scaffold (a frontend, a demo) that exercises a platform
in another repo, **I want** to declare both trees, **so that** the loop builds the
scaffold AND sculpts the platform where the scaffold reveals a gap, with the gate
holding both honest.

**Acceptance Criteria:**
- [ ] A config with `[target]` (scaffold) + one `[sculpts.platform]` (the other
      repo) runs a burndown that commits scaffold changes to the scaffold repo and
      platform changes to the platform repo, each on its declared branch
- [ ] `recurve matrix --gate` is green only when the scaffold probes AND the
      platform's own gate both pass (federation)
- [ ] Each tree enforces its own `forbidden_strings`
- [ ] Adversarial: a cycle that breaks the platform's gate turns the federated gate
      RED even if the scaffold probe is GREEN

### US-3: A non-Rust (web/node) target
**As** a developer with a web app, **I want** freshness and rebuild to fit a bundle,
not a binary, **so that** probes are never run against a stale build and I never
hand-write a content-hash rule that doesn't apply.

**Acceptance Criteria:**
- [ ] `--kind web` selects a source-hash (or build-output) `reads` method, not
      `content-hash`-over-a-binary
- [ ] `rebuild` defaults to the kind's build command (`npm ci && npm run build`)
- [ ] Adversarial: changing a source file without rebuilding marks the relevant
      probes STALE, not GREEN

### US-4: The generated workflow just runs
**As** a developer, **I want** the burndown workflow `init` stamps to run unmodified
under its runtime, **so that** I don't debug the tool's own template at 4am.

**Acceptance Criteria:**
- [ ] The generated workflow contains no runtime-forbidden call (e.g. wall-clock /
      RNG that the sandbox bans)
- [ ] The generated workflow resolves all paths from the suite root regardless of
      the launching cwd
- [ ] The generated workflow finds the `recurve` binary without a hand-made symlink
- [ ] Adversarial: launching the stamped workflow from an unrelated cwd still
      completes preflight

### US-5: Drafts you can baseline after a skim, not a rewrite
**As** the human owner of a spec, **I want** claimify drafts that are coherent units
with real first-draft fixes, **so that** review is a skim, not a rewrite.

**Acceptance Criteria:**
- [ ] One claim per logical requirement (bullet / sentence), never split mid-unit
- [ ] Titles are summarized to fit, never truncated mid-word
- [ ] `smallest_fix` carries the requirement's own imperative as a first draft, not
      a bare `TODO`
- [ ] Only requirements that *loosen* a check are `security-tradeoff`; ones that ADD
      a check are `missing-surface`
- [ ] Adversarial: a spec whose bullets wrap across source lines still yields one
      claim per bullet

## 4. Functional Requirements

### A — Init & config wiring

- **FR-A1:** `init` and `claimify` share ONE prefix derivation; the emitted
  `forbidden_strings` includes that exact claim prefix, `recurve`, and the source
  spec's filename + section-reference markers. Twin: a claim id or a `<spec> §N`
  reference pasted into product code fails the leak guard.
- **FR-A2:** `init` writes a config with no required field left as a placeholder for
  the target's kind; a post-init `recurve validate` passes immediately. Twin: a
  required field emitted empty fails the post-init check.

### B — Target-type awareness

- **FR-B1:** `recurve init --kind web|rust|node|generic` (default inferred from the
  tree: a `package.json` → node/web, a `Cargo.toml` → rust) selects the kind's
  `reads` method, `rebuild` command, and `forbidden_strings` baseline. Twin: a web
  tree initialized with a binary `content-hash` rule fails validate with a
  kind-mismatch message.
- **FR-B2:** claimify uses the kind to bias class/severity and probe hints (a web
  spec's "looks/renders" claims map to render/static checks, not binary probes).
  Twin: a web claim scaffolded with a "build the binary" probe hint is flagged.

### C — The multi-tree feedback model (centerpiece)

- **FR-C1:** the config supports `[target]` (the PRIMARY tree the loop builds) plus
  zero-or-more `[sculpts.<name>]` (secondary trees in possibly-other repos the loop
  may sculpt when a claim's fix requires it). With no `[sculpts.*]`, behavior is
  byte-for-byte today's single-tree behavior. Twin: an existing single-tree config
  validates and runs unchanged.
- **FR-C2:** a cycle that fixes a primary-tree gap commits to the primary repo; a
  cycle whose fix requires a sculpt target commits that change to the sculpt repo on
  the sculpt's declared branch — one commit per repo touched, never cross-tree
  changes in one commit. Twin: a single commit mixing primary and sculpt trees fails
  the boundary check.
- **FR-C3:** `recurve matrix --gate` **federates** — it is green only when the
  primary tree's probes AND every declared sculpt target's own gate command pass.
  Twin: a sculpt that breaks the platform's gate makes the federated gate RED even
  though the primary probe is GREEN.
- **FR-C4:** each tree (primary and every sculpt) carries its OWN
  `forbidden_strings`, commit branch/policy, and freshness rule; a leak or staleness
  in any tree is attributed to that tree. Twin: a planning token in the sculpt tree
  fails even when the primary tree is clean.
- **FR-C5:** a claim may declare which tree(s) it touches (`touches: [primary,
  platform]`); freshness and the gate consult only the declared trees' rules, and an
  un-declared tree mutation is flagged. Twin: a cycle that edits a tree the claim did
  not declare is reported as scope leakage.

### D — Claimify

- **FR-D1:** decomposition is by **logical unit** — continuation lines are merged
  into their bullet/sentence before a claim is emitted; never one-claim-per-raw-line.
  Twin: a bullet that wraps across two source lines yields exactly one claim.
- **FR-D2:** titles are summarized to the length budget on a word boundary with a
  meaningful head, never a mid-word truncation. Twin: a long requirement yields a
  readable title, not an ellipsis mid-token.
- **FR-D3:** `smallest_fix` is seeded from the requirement's own imperative (a real
  first draft), not a bare `TODO`. Twin: an emitted draft whose `smallest_fix` is
  literally `TODO` fails a claimify self-check in `--strict` mode.
- **FR-D4:** a requirement is `security-tradeoff` only when it *loosens* an existing
  check; one that ADDS a fail-closed check is `missing-surface`. The classifier
  distinguishes the two (loosen-verbs vs add/enforce-verbs), defaulting to
  `missing-surface` on ambiguity, surfaced for review. Twin: an "add a check"
  requirement marked review-gated is corrected (or flagged) by the classifier.

### E — Generated-workflow correctness

- **FR-E1:** the stamped burndown workflow contains NO runtime-forbidden call (no
  wall-clock/RNG the sandbox bans); ids and labels are derived deterministically.
  Twin: the template emitting a banned call fails a template lint.
- **FR-E2:** the stamped workflow resolves every path from the **absolute suite
  root** (written in at init time) and is independent of the launching cwd. Twin:
  launching it from an unrelated directory still completes preflight.
- **FR-E3:** the stamped workflow invokes `recurve` via a configurable binary path
  (honoring `RECURVE_BIN`, defaulting to the resolved install), never a bare name
  that assumes PATH. Twin: with `recurve` absent from PATH but `RECURVE_BIN` set, the
  workflow still runs.

### F — Install / PATH

- **FR-F1:** a documented one-liner puts `recurve` on PATH (`pipx install .` /
  `uv tool install .` / a `recurve install` shim); the docs name it. Twin: a fresh
  environment following the documented install resolves `recurve --version`.

### G — Documentation (how to use it)

The features above change *how you use* recurve; the docs are a deliverable, gated
like everything else. (Tonight, learning the existing surface required reading the
source — `claimify.py`, `init.py`, `config.py`, `burndown.js`. That is the gap.)

- **FR-G1:** every shipped config key and CLI flag is documented, and the docs
  reference no key/flag the tool does not ship — a **docs-drift check** compares the
  documented surface to the real `--help` + schema. `--kind`, `[target]`/`[sculpts.*]`,
  the new `reads` methods, and the install one-liner each appear in the usage docs
  with a worked example. Twin: a doc that references a removed flag, or omits a
  shipped one, fails the docs-drift check.
- **FR-G2:** `init` stamps **target-shaped** guidance — the generated `RUN.md` /
  `README` reflect the target's `kind` and tree topology. A multi-tree init's
  `RUN.md` explains the primary + sculpt trees, per-tree commits, and the federated
  gate; a single-repo init's mentions no trees it doesn't have. Twin: a multi-tree
  init whose `RUN.md` describes only one tree fails a template check.
- **FR-G3:** two **runnable** docs exist and are verified, not asserted — a
  **quickstart** ("first loop in one command" for a single repo) and a
  **feedback-loop worked example** (scaffold-sculpts-platform across two repos). The
  quickstart, run verbatim in a clean checkout, reaches a green BOOT cycle. Twin: a
  quickstart step that references an unbuilt command or unshipped flag fails when
  executed.
- **FR-G4:** the docs are **dogfooded as claims** — each load-bearing usage truth
  ("`--kind web` selects `source-hash`", "`[sculpts.*]` federates the gate") is a
  probe over the real tool, so documentation cannot silently drift from behavior.
  Twin: a doc-claim whose probe goes RED blocks release.

### H — Run ergonomics & observability (a run must be legible)

A greenfield run spends its first wave authoring probes with nothing in the product
tree yet — correct (the burndown IS the build; tests come first), but it reads as
"stuck" to anyone watching the product directory. And once it IS running, a human
should be able to ask "how far along, how much longer?" and get a real answer *from
the tool* — not compute it from commit timestamps by hand.

- **FR-H1:** a greenfield run surfaces progress *before* the first product-tree
  change. The arming wave emits a running count of probes authored (and for which
  gaps), and/or the bootstrap interleaves so the first scaffold (the app skeleton)
  lands early rather than only after every probe is written. Observable: within the
  first arming wave the run has logged authored-probe progress AND/OR the product
  tree has its first scaffold — never a long silent stretch with an empty tree and no
  signal. Twin: a greenfield run that finishes an entire arming wave with zero
  product-tree change and zero progress log is flagged as "looks stuck."
- **FR-H2:** `recurve report` answers "how far, how long?" with real numbers — it
  records true per-cycle wall-clock on the run-record and projects an ETA (remaining
  workable gaps × trailing-median cycle time, plus any pending arming waves and a
  note for park-prone integration cycles). Because the orchestrator runtime forbids
  reading a wall-clock mid-run (the same ban as FR-E1), durations are stamped from
  OUTSIDE the sandbox (or carried on the run-record), never read from a banned call
  inside it. Observable: after a few cycles, `report` shows non-zero per-cycle
  durations and a concrete ETA. Twin: a `report` whose cycle durations are all `0s`
  and whose ETA is blank while cycles demonstrably took minutes is flagged as a
  measurement bug.

## 5. Non-Goals (v1)

- **No remote/distributed orchestration.** Multi-tree means multiple local repos
  under one loop, not agents across machines.
- **No general build-system plugin API.** The `kind` presets cover web/rust/node;
  `generic` is the escape hatch (you set `reads`/`rebuild` yourself).
- **No change to the probe contract** (GREEN 0 / RED 1 / BROKEN 2, traps,
  per-cycle commits) or the draft → baseline ceremony.
- **No auto-merge across trees.** The gate is the serialization point; cross-tree
  fixes are still one human-reviewable commit per repo.

## 6. Design Considerations

### Config schema — single repo (unchanged)

```toml
[target]
tree = "."
kind = "rust"                # NEW, optional; inferred if omitted
forbidden_strings = ["GAP-", "WIT-", "recurve"]
rebuild = "cargo build --release"

[target.reads.cli]
method = "content-hash"
artifact = "bin/app"
source = "target/release/app"
```

A config with only `[target]` is exactly today's model. Nothing below is required.

### Config schema — scaffold-sculpts-platform (the feedback loop)

```toml
[target]                                  # the PRIMARY tree the loop BUILDS
tree = "web"
kind = "web"
forbidden_strings = ["GAP-", "FE-", "recurve", "PRD", "§"]
rebuild = "npm ci && npm run build"

[target.reads.bundle]
method = "source-hash"                    # NEW method: hash a source glob
sources = ["web/app/**", "web/components/**", "web/tokens.css"]

[sculpts.platform]                        # a SECONDARY tree in another repo
tree = "../auths"
kind = "rust"
branch = "dev-platform"                   # commits land here
forbidden_strings = ["GAP-", "WIT-", "recurve"]
rebuild = "cargo build --release -p app --features x"
gate = "cargo xtask check && ../demos/rictl matrix --gate"   # its OWN gate, federated

[commit]
policy = "unsigned-per-cycle"
```

Mental model: **`[target]` = what you build; `[sculpts.*]` = what you feed.** The
loop drives the target's claims; when a claim's honest fix is in a sculpt tree, the
cycle sculpts there and commits to that repo on its branch. `matrix --gate` ANDs the
target probes with every sculpt's `gate`. Single-repo just omits `[sculpts.*]`.

### `kind` presets

| kind | default `reads` | default `rebuild` | claimify bias |
| --- | --- | --- | --- |
| `rust` | `content-hash` over the release binary | `cargo build --release` | binary/CLI probes |
| `web` | `source-hash` over the source glob | `npm ci && npm run build` | render / static / a11y probes |
| `node` | `source-hash` (or `build-output`) | `npm ci && npm run build` | CLI / API probes |
| `generic` | `none` (you wire it) | `""` (you wire it) | no bias |

### New `reads` methods

- `source-hash` — freshness = digest of a declared source glob; a probe is STALE when
  the sources changed since the last rebuild. (Non-binary targets.)
- `build-output` — freshness = digest of a build-output path (e.g. `.next/`,
  `dist/`). For targets whose build is deterministic enough to hash.
- existing `content-hash` / `none` unchanged.

## 7. Technical Considerations

- **Backward compatibility is a hard gate.** The loader must read every existing
  `recurve.toml` (no `kind`, no `[sculpts.*]`) identically. New keys are optional
  with today's behavior as the default. A regression test pins an unchanged config's
  parsed `Config` object.
- **The prefix is one function.** `init` and `claimify` import the same
  `claim_prefix(suite)`; `forbidden_strings` is composed from its output so the two
  can never drift (FR-A1).
- **Federation reuses the existing gate.** A sculpt's `gate` is just a command whose
  exit code the federated `matrix --gate` ANDs in — the same mechanism the demos /
  interop / witness suites already use across `../auths`.
- **The workflow template is data, not prose.** Generating it through one builder
  that a template-lint checks (no banned calls, absolute root, `RECURVE_BIN`) makes
  FR-E* structural, not a checklist.
- **Dogfood.** This very file is the claimify input; running the improved `init
  --kind generic --from-prd docs/improvements.md` against a checkout of recurve and
  burning it down is the acceptance demo.

## 8. Success Metrics

- A fresh `recurve init --kind web` needs **zero** manual `recurve.toml` edits before
  `baseline` (today: 4+).
- The stamped burndown workflow runs **unmodified** (today: 5 hand-patches were
  required).
- claimify drafts on a bullet-list spec need a **skim**, not a rewrite — measured as
  ≤1 edited field per draft on review (today: a full rewrite of 22 drafts).
- An existing single-tree suite's `matrix --gate` output is **byte-identical** before
  and after the upgrade (backward-compat proof).
- A scaffold-sculpts-platform config closes a claim by committing to **two repos** in
  one cycle, with the federated gate green.

## 9. Open Questions

1. **Claim ownership of trees:** explicit `touches:` per claim (FR-C5) vs inferred
   from what the cycle edited? (v1: optional `touches:`, inferred + flagged if
   omitted.)
2. **Sculpt-gate cost:** running every sculpt's full gate each cycle can be slow. Do
   we cache per-tree gate results keyed on that tree's freshness digest? (Likely yes,
   reusing the `reads` digest.)
3. **Prefix collisions:** `FE-`, `W-` as `forbidden_strings` can over-match legit
   product strings. Should the guard be anchored (word-boundary / id-shaped) rather
   than raw substring? (Probably yes — fixes a latent false-positive risk.)
4. **`kind = web` design-gate probes** need a headless browser. Does `init --kind
   web` offer to add it to the harness, or stay static-only by default and let a
   claim pull it in? (Lean: static-first; a render probe declares the dependency.)

---

## Appendix A — Claim-block map (for the claimify pass)

| Block | Claims (sketch) | Kind |
| --- | --- | --- |
| INIT | config fully wired; shared prefix; no placeholders (FR-A1/A2) | tooling |
| KIND | kind presets for reads/rebuild/forbidden; claimify bias (FR-B1/B2) | tooling |
| TREE | `[target]` + `[sculpts.*]`; per-tree commit/forbidden/gate; federation; backward-compat (FR-C1..C5) | architecture |
| CLAIM | logical-unit splits; titles; real fixes; loosen-vs-add classifier (FR-D1..D4) | claimify |
| FLOW | sandbox-safe, cwd-absolute, `RECURVE_BIN`-honoring generated workflow (FR-E1..E3) | tooling |
| PATH | documented install one-liner (FR-F1) | docs/packaging |
| DOCS | usage docs match the shipped surface; quickstart + feedback-loop examples run; templates are kind/topology-shaped (FR-G1..G4) | docs |
| RUNUX | a run is legible: arming progress / early scaffold (FR-H1) + `report` answers how-far/how-long with real durations + ETA (FR-H2) | UX / obs |

## Appendix B — Traceability to the observed friction

| Friction hit in practice | Addressed by |
| --- | --- |
| claimify split §6 by raw lines; truncated titles; `TODO` fixes | FR-D1, FR-D2, FR-D3 |
| `forbidden_strings` guarded `web-` while ids were `W-`; missed `PRD §` | FR-A1 |
| over-flagged 6 design claims as review-gated | FR-D4 |
| `init` left `tree`/`reads`/`rebuild` stubs ("now edit recurve.toml") | FR-A2, FR-B1 |
| binary-only `content-hash` reads model for a web bundle | FR-B1, new `source-hash`/`build-output` |
| generated workflow threw on a banned runtime call | FR-E1 |
| generated workflow assumed cwd = suite root | FR-E2 |
| `recurve` not on PATH; hardcoded `PROG='recurve'` | FR-E3, FR-F1 |
| no first-class model for frontend-builds-here, sculpts-platform-there | FR-C1..C5 (the centerpiece) |
| learning the existing surface required reading recurve's source (claimify/init/config/burndown) | FR-G1, FR-G4 (docs match the tool) |
| a greenfield run authored 11 probes with an empty product tree + no progress signal — read as "stuck" | FR-H1 |
| `recurve report` showed 0s cycle durations + a blank ETA; I computed the ETA from commit timestamps by hand | FR-H2 |

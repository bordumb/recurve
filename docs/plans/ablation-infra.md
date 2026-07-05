# PRD — ablation infrastructure: ports, adapters, and isolation for adversary/governor

> Scope: `recurvelib` **the engine's internal architecture**. This is the
> *how* to `oracle-strength-and-decorrelation.md`'s *what* (R2 adversary,
> R5 governor) and to `eval-full.md` §4's arms A7–A10. Without this PRD,
> those requirements risk landing as bespoke, one-off code wired into the
> burndown loop — which would make the *next* switch expensive to add,
> defeating the point of an ablation matrix. This PRD makes adding switch
> N+1 a new adapter file, not a change to the loop.

> **Build order across both PRDs** (read
> [oracle-strength-and-decorrelation.md](oracle-strength-and-decorrelation.md)
> first for the *why*; this one for the *how*; build in this order
> regardless of which you read first):
>
> 1. **R1 + R3** in the other PRD — oracle tier vocabulary,
>    authoring-time nudge. Build first, independently: neither needs any
>    new port/protocol, both just render/derive from mechanisms that
>    already exist (`drill --diff`, `drill --fuzz`, `oracle_waiver`).
> 2. **This PRD's scaffolding**: AI1 (protocols) → AI3 (snapshot
>    mechanism) → AI4 (isolation strategy) → AI11 (shared reviewer
>    plumbing) → AI7 (uniform provenance, both tiers).
> 3. **AI2** — the registry plus the concrete
>    `off`/`same_model`/`cross_model`/`mechanical`/`mechanical_review`
>    adapters. This is what satisfies the other PRD's **R2** and **R5**
>    automated tiers.
> 4. **AI6** — `human_required`, once AI7's cryptographic tier and the
>    real `auths-core` reuse are in place. Satisfies **R5**'s third tier.
> 5. **AI9 + AI10** — the policy floor and the mechanical-tier default,
>    once the tiers above exist to floor/default toward.
> 6. **AI8** — fold **R4**'s reversal event into the unified
>    `challenge_event` schema now that the veto event (R5/AI6) exists to
>    unify with.
> 7. **AI5** — wire `eval/evallib`'s arm composer to the same registry,
>    unblocking `eval-full.md`'s A7–A10.
> 8. **Last, the finish line for both PRDs**: author the O6-incident
>    regression fixtures — at claim level (R2) and run level (R5) — and
>    prove them green using the real adapters this order built. Neither
>    PRD is done until these pass.

## 0 · This completes an intention the codebase already states

`recurvelib/loop/runtime.py`'s own module docstring already says it:

> "the actor that proposes diffs and the adversary that red-teams claims
> are pluggable agents behind protocols"

That sentence is aspirational today — `Actor(Protocol)` exists
(`def propose(self, contract, item, evidence): ...`), `World(Protocol)`
exists, and the **capture rule** (`capture(trap_red_on_wrong,
trap_green_on_real)`) already independently validates any proposed
counterexample regardless of who proposes it — but no `Adversary`
protocol has ever been defined, and no `Governor` concept existed before
`oracle-strength-and-decorrelation.md`'s R5. This PRD is not introducing
ports/adapters to recurve as a foreign pattern — it's **finishing a
design the engine already declared**, extended to cover the run-level
governor the O6 incident showed was also necessary.

**Written pre-launch.** There are no existing deployments to preserve
compatibility with. Where a cleaner design requires a breaking change — a
new `Protocol` method, a merged ledger schema, a changed default — this
PRD takes it, and says so explicitly (marked *pre-launch simplification*
at each such point) rather than staging it behind a flag for a migration
that will never happen.

## 1 · The pattern already exists four times; name it, then reuse it

| Existing extension point | The "port" | The "adapter" |
|---|---|---|
| A probe | *any executable* satisfying the exit-code + `TRAP_FIXTURE`/`ISO_FIXTURE` env contract | a bash script, a Python script, anything |
| The acting agent | `Actor(Protocol).propose(...)` | the concrete class that shells out to `AGENT_CMD` (`claude -p ...`) |
| A stronger reference oracle | `Gap.reference` (a path `drill --diff` invokes) | whatever executable lives at that path |
| The eval's BigCodeBench oracle | `RECURVE_ORACLE_PYTHON`/`RECURVE_ORACLE_IMAGE` | the warm-container wrapper |

Every one of these is already "bring your own implementation, honor the
contract." **This PRD's job is to add the two rows the ablation matrix
needs — `Adversary` and `Governor` — in exactly this shape**, not invent
a new architectural style.

## 2 · The two new ports

Defined as `Protocol`s alongside `World`/`Actor` in `recurvelib/loop/`
(same module or an immediate sibling — match wherever `Actor` itself
lives once implemented; do not create a parallel protocol-definition
location):

```python
class Adversary(Protocol):
    """A pluggable, decorrelated reviewer. Given a claim's committed
    artifacts (never the acting agent's live session), it either finds
    nothing, or proposes a counterexample for the EXISTING capture rule
    to independently validate — this port never certifies anything
    itself; capture() still does that."""

    def review(self, claim: "ClaimSnapshot") -> "AdversaryVerdict": ...


class Governor(Protocol):
    """A pluggable, superseding check on a cycle's decision to report
    STOP_SUCCESS. Given the cycle's newly-green claims as committed
    artifacts, plus a fresh-checkout re-execution capability, it clears
    the batch or vetoes specific claims with a reason."""

    def audit(self, cycle: "CycleSnapshot") -> "GovernorVerdict": ...
```

`AdversaryVerdict` = `no_objection | proposed_trap(fixture, rationale)`.
`GovernorVerdict` = `cleared | veto({claim_id: reason})` — a veto's
reason is exactly what R5 requires to become a captured trap, never a
bare rejection.

Note what this buys for free: **the capture rule already does the hard
validation work** (`trap_red_on_wrong ∧ trap_green_on_real`) regardless
of what proposed the trap. `Adversary.review()` only has to *propose*;
it never has to be trusted. Decorrelation is therefore only a concern
for the *proposing* step — which is exactly what §4–5 below secure.

## 3 · Adapters and the registry — the extensibility property

Concrete adapters live in a new `recurvelib/adapters/` package (mirrors
`core/analysis/io/loop`, sibling to them — protocols stay near the loop
they serve; implementations that shell out to subprocesses/containers
stay separate so the loop never imports `subprocess`/docker SDKs
directly):

```
recurvelib/adapters/
  _shared/              # written once, composed by adversary/ and governor/ (AI11)
    reviewer_base.py      # isolation + snapshot + provenance wiring shared by both
    identity.py            # mint_human/mint_agent, is_human_identity/is_agent_identity
                           # (borrows auths-curve's src/auths_curve/integration.py pattern)
    provenance.py           # the two-tier Provenance envelope (AI7): metadata_verified |
                           # cryptographically_attested (auths sign_verdict/verify_verdict)
  adversary/
    off.py          # no-op: always no_objection (today's default behavior)
    same_model.py    # isolated review, no cross-model identity requirement
    cross_model.py   # isolated review + verified-different-model check
  governor/
    off.py
    mechanical.py     # fresh-checkout re-execution of the cycle's probes+traps
    review.py          # decorrelated-model batch review over the cycle
    human_required.py  # async: pending_human_signoff -> auths-signed approval (AI6)
  isolation/           # shared strategy, used by both adversary/ and governor/
    subprocess_tempdir.py   # default
    docker.py                # opt-in, for adapters needing a heavy pinned runtime
  snapshot.py           # ClaimSnapshot/CycleSnapshot construction (§5)
```

Resolution is a small string-keyed registry, not a plugin-discovery
system (house rule: don't build for hypothetical requirements — a
dict is enough until third-party out-of-tree adapters are a real need,
at which point Python entry points are the natural upgrade, matching
the framework paper's §7.3 portable-claims ambition):

```python
ADVERSARY_ADAPTERS = {"off": NoOpAdversary, "same_model": SameModelAdversary,
                      "cross_model": CrossModelAdversary}
GOVERNOR_ADAPTERS  = {"off": NoOpGovernor, "mechanical": MechanicalGovernor,
                      "mechanical_review": MechanicalReviewGovernor,
                      "human_required": HumanRequiredGovernor}
```

`[gate] adversary = "cross_model"` / `[gate] governor =
"mechanical_review"` resolve through these registries. **The load-bearing
property**: `recurvelib/loop/runtime.py` depends only on the `Adversary`/
`Governor` protocols, never on a concrete adapter class or on `subprocess`/
docker directly — adding adapter N+1 is a new file plus one registry
line, with zero changes to the loop, the controller, or `decide()`.

**One registry, two consumers — no duplication.** `eval/evallib`'s arm
composer (`arms.py`) must resolve `adversary=`/`governor=` through this
*same* registry (imported from `recurvelib`), not reimplement adversary/
governor logic independently inside `eval/`. `eval-full.md`'s A7–A10 and
`/recurve-work`'s own gate config are two callers of one implementation,
exactly like `AGENT_CMD` already serves both today.

## 4 · Does the adversary need Docker? No — and here's the precise reason

Isolation here has two independent dimensions, and conflating them is
what makes "does X need Docker" feel like a bigger question than it is:

- **Process isolation is already free.** Every existing port in §1 is
  invoked as an *external process* (`AGENT_CMD` shells out; the oracle
  runs in a container). Fresh process = no shared Python memory, no
  shared conversation, by construction, with zero extra engineering —
  this is already true the moment `Adversary`/`Governor` are implemented
  as anything that shells out rather than an in-process function call.
- **Filesystem/context scope** — *what the process can see* — is the
  actual design question, and it's answered in §5, not by Docker.
  A plain subprocess given a **freshly populated, read-only temp
  directory** achieves the same scoping guarantee a container's mount
  namespace does, at far lower cost, *for this workload*.
- **Docker earns its place for the BigCodeBench oracle** because that
  adapter has a genuinely heavy, exotic, version-pinned requirement
  (Python 3.10, tensorflow, opencv, tesseract, a specific numpy — see
  `eval-optimize.md`) that must be reproducible across machines. An
  adversary/governor adapter is fundamentally *an LLM API call reviewing
  text and code* — it needs a language client and network egress to
  reach its provider, not a pinned scientific-computing runtime.

**One asymmetry worth stating plainly**: the oracle runs with
`--network=none` (it executes untrusted generated code and must not
phone home); an adversary/governor adapter needs the *opposite* —
network egress to its own model API — while still having *zero*
filesystem access to the acting agent's session. "Isolated" does not
mean "no network" uniformly; it means "no access to what it shouldn't
see," and what it shouldn't see is a filesystem/context question, not a
network question.

**Conclusion**: `isolation/` is its own pluggable strategy
(`subprocess_tempdir` default, `docker` opt-in), selected **per adapter**,
not mandated globally. An adapter that needs a heavy runtime (a future
`kernel_verified` governor requiring a Lean install, say) opts into
`docker`; `cross_model`/`mechanical_review` do not need to.

## 5 · How context is shared when the reviewer is isolated

This is the actual engineering content of "decorrelation," and it has a
precise, single mechanism: **a `ClaimSnapshot`/`CycleSnapshot` is a
`git archive` of the pinned commit at which the claim/cycle closed,
extracted into a fresh temp directory and mounted read-only.** One
mechanism serves all three consumers (R5's mechanical re-execution tier,
R5's review tier, and R2's per-claim adversary) rather than three ad hoc
context-passing schemes:

- **Why a commit, not hand-picked files.** Probes and solutions have
  file dependencies (shared helpers, imports); enumerating a minimal
  file subset is fragile. The full tree at a pinned commit is simple,
  robust, and *still* excludes exactly what must be excluded, because
  `git archive` only ever contains tracked, committed content.
- **What this structurally excludes, for free**: the acting agent's live
  process, its conversation/reasoning trace, its uncommitted scratch
  files, and any other claim's concurrent in-flight state. None of that
  is ever committed, so none of it is ever in the archive. The exclusion
  boundary is not a filter to get right — it's a property of what `git
  archive` can contain at all.
- **The one explicit knob this reveals, worth naming**: should an
  adversary in "attempt to refute" mode **see the claim's existing
  traps**? Seeing them risks the adversary paraphrasing a known
  counterexample instead of finding a genuinely new blind spot (weaker
  decorrelation); *not* seeing them risks wasted rediscovery. Default:
  **withhold existing traps from a refuting adversary** (optimize for
  novel blind-spot discovery); a governor's *mechanical* tier, by
  contrast, must re-execute existing traps (that is its entire job), so
  its snapshot includes them. This is a config field on the snapshot
  builder (`include_existing_traps: bool`), not a hardcoded choice.

## 5a · Cryptographic identity: borrowing auths-curve's signer/witness seam

A working, offline-verifiable identity-and-signing seam already exists in
this workspace — `auths-curve` (`src/auths_curve/integration.py`,
`tools/auths_sign_receipt.py`) — built for a different purpose (an auths
agent identity signs off on recurve's own gate verdicts) but directly
reusable here, not reinvented:

- **`mint_agent`/`is_agent_identity`** already mint a `did:keri:` identity
  carrying a **capability attestation** marking it as an agent, and check
  for that attestation's presence — this PRD adds the mirror,
  **`mint_human`/`is_human_identity`**, marked by a *positive* human
  capability attestation (not the mere absence of an agent one — presence
  checks are harder to spoof than absence checks, same principle as R1's
  anti-gaming traps).
- **`sign_verdict`/`verify_verdict`** already produce and check a tamper-
  evident, offline-verifiable action envelope over an arbitrary payload
  (today: a recurve gate verdict). AI6's human sign-off reuses this exact
  pair unchanged, just pointed at a different payload (a governor
  approval record).
- **The witness cosignature is already this PRD's R2, shipped, for a
  different role.** `auths-curve`'s docs state the principle directly:
  "the witness identity differs from the signer's — the whole point...
  so the referee cannot quietly bless its own work." That *is*
  cross-model decorrelation — for signing rather than authoring. AI7
  folds it back: a cryptographic signature from a distinct, known key is
  **non-repudiable** in a way "the API said a different model served
  this" is not — strictly stronger than R2's metadata-based identity
  check.
- **Correction (verified against source, not assumed): the biometric gate
  already exists, in production, one directory over — reuse it, don't
  build it.** `auths-curve`'s own identity path (`mint_agent`) is
  deliberately headless/passphrase-derived, because it signs *automated*
  recurve verdicts with no human present — that part has no biometric
  gate, correctly. But the sibling `auths` repo's real CLI already does
  exactly what AI6 needs: `crates/auths-core/src/storage/secure_enclave.rs`
  ("Signing triggers Touch ID / Face ID," handling
  `"biometric authentication failed or cancelled"` as a real error case),
  plus `macos_keychain.rs`/`ios_keychain.rs`/`android_keystore.rs` and the
  `auths-cli/src/bin/sign.rs` entrypoint — this is the exact mechanism
  behind `auths sign`/`auths init`'s daily, real, Touch-ID-gated commit
  signing. `mint_human`'s key must be stored via **this** backend (SE on
  macOS, StrongBox/Titan on Android/iOS via the same storage crate), never
  `auths-curve`'s passphrase-derived KDF — the human/agent distinction is
  then not just a different capability attestation but a different key
  *storage backend*, matching how these identities actually differ in
  practice today.

## 6 · Requirements

### AI1 — The two ports exist; nothing existing changes

**Assertion.** `Adversary`/`Governor` protocols are added; `World`,
`Actor`, `capture()`, `within_boundary()`, `guarded_propose()` are
untouched — byte-identical behavior for every existing claim.

**Counterexamples (traps).** A diff to this PRD's implementation that
touches `capture()`'s logic must be refused (capture-rule regression
fixture: existing capture() unit behavior must be unchanged). Any new
code path that lets an adapter certify a claim GREEN directly, bypassing
`capture()`, must be refused — proposal and validation stay separated.

**Bounds.** Purely additive; default adapters (`off`) reproduce today's
behavior exactly.

### AI2 — Adding an adapter never touches the loop

**Assertion.** A new adapter (a new file in `adapters/adversary/` or
`adapters/governor/` plus one registry line) is invokable via config
alone — `recurvelib/loop/runtime.py`, `controller.py`, and `decide()`
require zero changes.

**Counterexamples (traps).** A grep-based fixture: after adding a
deliberately trivial new adapter (e.g., a test-only `"echo"` adversary),
`git diff` against `runtime.py`/`controller.py` must be empty. A registry
entry pointing at an adapter that doesn't implement the full protocol
(missing `.review()`/`.audit()`) must fail at registration time, not at
first invocation mid-run.

**Bounds.** The registry is a plain dict now; entry-point-based
third-party discovery is a documented future upgrade, not built here.

### AI3 — Context snapshots enforce the exclusion boundary mechanically

**Assertion.** `ClaimSnapshot`/`CycleSnapshot` are built only from
`git archive <pinned-commit>`; the builder never accepts a live working
directory path as its source.

**Counterexamples (traps).** A snapshot builder invoked against a dirty
working tree (uncommitted changes present) must refuse or must
demonstrably archive only the pinned commit's tree, not the working
directory's current state (dirty-tree fixture). A crafted commit that
plants the acting agent's scratch/session files under tracked paths
(attempting to smuggle context through the exclusion boundary) is
out of scope for *this* mechanism — flag it as a residual risk for
`within_boundary()`-style write-boundary enforcement to consider, not
solved here.

**Bounds.** One mechanism, three consumers (§5) — no per-consumer
context-building code.

### AI4 — Isolation strategy is pluggable and per-adapter, not global

**Assertion.** `subprocess_tempdir` is the default isolation strategy for
`adversary/` and `governor/` adapters; `docker` is available and
selected per-adapter (not per-run, not globally) for adapters whose
implementation declares a heavy-runtime requirement.

**Counterexamples (traps).** An adapter using `subprocess_tempdir` must
be shown to have no filesystem access beyond its mounted snapshot
(isolation-boundary fixture, same shape as R2's). Selecting `docker` for
an adapter that doesn't need it must not be silently required by the
harness — the strategy choice lives with the adapter's own declared
needs.

**Bounds.** Reuses the eval's own isolation lessons (`eval-optimize.md`
O1/O2) where applicable (warm-container pattern, digest pinning) *if and
only if* a future adapter chooses the `docker` strategy — not imposed on
adapters that don't need it.

### AI5 — One registry, two consumers, no duplication

**Assertion.** `eval/evallib`'s arm composer resolves `adversary=`/
`governor=` by importing and calling this registry from `recurvelib`,
not by reimplementing adversary/governor logic inside `eval/`.

**Counterexamples (traps).** A drift fixture: `eval/evallib`'s arm
composer must fail to import if it defines its own
`ADVERSARY_ADAPTERS`/`GOVERNOR_ADAPTERS` mapping rather than importing
`recurvelib`'s — a lint-shaped check, not a runtime one.

**Bounds.** `eval/` remains its own uv project (`recurvelib` stays
stdlib+PyYAML); the dependency is one-directional (`eval` imports
`recurvelib`, never the reverse).

### AI6 — Human-required governance, cryptographically attested (pre-launch simplification: async verdict state)

**Assertion.** `governor = "human_required"` is a real adapter (§5a). Its
verdict adds a third state beyond `cleared`/`veto`:
**`pending_human_signoff`** — human review is asynchronous by nature, so
`audit()` cannot block the loop waiting for it. On
`pending_human_signoff`, the cycle stays in `PENDING_GOVERNOR` and the
loop **suspends cleanly** (exits, does not busy-wait) rather than
spinning. A separate command, `recurve governor approve <claim_id>
--attestation <path>`, resumes it. The attestation is an auths-signed
envelope (§5a) over `{cycle_snapshot_hash, claim_ids, decision,
rationale}` — bound to the exact reviewed artifact by its content hash —
and it must be signed by a **human-attested identity**
(`is_human_identity()` true), never an agent-attested one.

**Counterexamples (traps).**
- An attestation whose signed `cycle_snapshot_hash` does not match the
  current snapshot must be refused (replay/drift fixture — an approval
  of v1 must not clear a claim silently modified to v2).
- An attestation signed by an agent-attested identity must be refused
  even if the signature otherwise verifies (identity-type fixture — a
  script cannot forge "a human looked at this" by minting itself a key).
- A `pending_human_signoff` cycle must not silently resolve to either
  `cleared` or `veto` on any timeout, cap, or default — it stays pending
  until an explicit, verified attestation arrives. No default-approve,
  no default-reject.
- A `min_governor_tier = "human_required"` claim (AI9) must be
  unaffected by a suite-wide `governor = "mechanical"` or `"off"`
  default — the floor holds regardless of the ambient config.

**Bounds.** Reuses `auths-curve`'s `sign_verdict`/`verify_verdict`
directly rather than inventing new cryptography (§5a), and reuses
`auths-core`'s existing, shipped, Touch-ID/Secure-Enclave-gated key
storage (`storage/secure_enclave.rs`, `macos_keychain.rs`) for the human
identity's key — the same mechanism already backing `auths sign` for
real daily commit signing. No new biometric integration work.

### AI7 — Uniform provenance: every port, not just adversary/governor; two tiers of strength

**Assertion.** `Actor`, `Adversary`, and `Governor` all return their
result alongside a **`Provenance`** object — closing the asymmetry where
R2/R5 verify the adversary/governor's identity *against* the actor's
logged identity, while the actor's own identity was never itself held to
the same standard. Provenance has two strengths, chosen per adapter:
**`metadata_verified`** (the served-model field from the provider's own
API response — cheap, the R2/R5 default) and
**`cryptographically_attested`** (an auths-signed envelope, §5a —
required for `human_required`, available as an upgrade for
`cross_model`/`mechanical_review` when the deployment wants the
witness-cosignature-grade guarantee rather than a trusted metadata
field).

**Counterexamples (traps).** A port claiming `cryptographically_attested`
provenance whose envelope fails to verify against the claimed identity's
public key must be demoted to unverified, never silently accepted. A
`cross_model` adversary configured for cryptographic attestation but
signing with the actor's own key must be refused — the same identity
check as R2's metadata trap, now enforced by signature instead of (or in
addition to) API response inspection.

**Bounds.** `metadata_verified` remains the default for the automated
tiers (cheap); `cryptographically_attested` is opt-in for them and
mandatory for `human_required`. R1's oracle-tier vocabulary is not
expanded further to track this distinction now (avoid tier-list bloat) —
noted as a natural future refinement if it proves useful in practice.

### AI8 — One challenge-event schema, not two (pre-launch simplification)

**Assertion.** `oracle-strength-and-decorrelation.md`'s R4 "reversal
event" and R5 "veto event" are the same concept at different points in
time — a GREEN challenged by a stronger check, either before the run
publishes success (veto) or after (reversal). Pre-launch, with no
existing ledger data to migrate, they are **one event type**,
`challenge_event`, carrying `phase: pre_publication | post_publication`,
the R1 tier held at challenge time, and — when the challenger was
human — a reference to the AI6 attestation. `recurve stats` reports one
combined rate, sliceable by phase.

**Counterexamples (traps).** An event recorded in either of the old,
separate reversal/veto shapes must fail schema validation — there is
deliberately no dual-schema compatibility path to preserve, since nothing
exists yet that depends on the old shape.

**Bounds.** This simplification is justified specifically by pre-launch
status; called out so a future contributor doesn't wonder why R4/R5 were
drafted with two schemas and shipped with one.

### AI9 — Policy floor: a claim can mandate a stronger tier than the suite default

**Assertion.** A claim (or a claim tag/category) may declare
`min_governor_tier`, which the effective tier for that claim resolves to
at **at least** — the suite-wide `[gate] governor=` default may
strengthen it further but never weaken it below the floor. This is how a
claim tagged e.g. `asserts_third_party_error` mandates `human_required`
regardless of whatever the operator's global config happens to be set
to.

**Counterexamples (traps).** A suite-wide `governor = "off"` must not
suppress a claim-level `min_governor_tier = "human_required"` — the
floor-override fixture: the claim's effective tier must still resolve to
`human_required`.

**Bounds.** Floors compose by max-strength only; a claim with no floor
uses the suite default exactly as today (no behavior change for the
common case).

### AI10 — The mechanical governor tier is default-on (pre-launch simplification: no legacy default to preserve)

**Assertion.** `[gate] governor` defaults to `"mechanical"`, not `"off"`.
Cost is zero (re-execution of work already done, no new agent calls),
and pre-launch removes the only reason to ship the weaker default —
there are no existing configs whose behavior this would silently change.

**Bounds.** `mechanical_review` and `human_required` remain opt-in or
floor-driven (AI9) — only the free tier's default changes.

### AI11 — Shared reviewer plumbing, written once

**Assertion.** Isolation-executor invocation, snapshot construction, and
provenance attachment are written once in
`adapters/_shared/reviewer_base.py`, and
`adversary/*.py`/`governor/*.py` adapters compose from it rather than
each reimplementing their own copy.

**Counterexamples (traps).** A lint-shaped check: a new adapter file that
constructs its own subprocess/snapshot/provenance logic instead of
importing `_shared.reviewer_base` should be flagged — a nice-to-have
static check, not a hard release gate.

**Bounds.** Internal code organization only; no external config surface
changes.

## 7 · Sequencing

AI1 (protocols) → AI3 (snapshot mechanism — needed by everything else)
→ AI4 (isolation strategy) → AI11 (shared reviewer plumbing, so AI2's
adapters compose from one implementation rather than three) → AI7
(uniform provenance, both tiers) → AI2 (registry + the concrete `off`/
`same_model`/`cross_model`/`mechanical`/`mechanical_review` adapters,
satisfying `oracle-strength-and-decorrelation.md` R2/R5) → AI6
(`human_required`, reusing AI7's cryptographic tier and §5a's auths seam)
→ AI9 (policy floor) and AI10 (mechanical default-on) → AI8 (challenge-
event schema unification) → AI5 (wire the eval's arm composer to the
same registry, unblocking A7–A10).

## 8 · Acceptance for the wave

- Gate GREEN; every new claim's probe demonstrated RED-first against its
  trap.
- The grep-based "adding an adapter touches nothing in the loop" fixture
  (AI2) passes for a deliberately trivial new adapter.
- The dirty-working-tree snapshot fixture (AI3) passes.
- `eval plan` on a manifest naming A7–A10 resolves `adversary=`/
  `governor=` through `recurvelib`'s registry with no `eval/`-local
  reimplementation (AI5).
- `oracle-strength-and-decorrelation.md`'s R2/R5 regression fixtures
  (the O6 replay, at claim level and run level) pass using the adapters
  this PRD builds — this PRD is done when that PRD's fixtures are green
  using real adapters, not stubs.
- The `human_required` async fixture (AI6) passes: a
  `pending_human_signoff` cycle suspends cleanly, resumes only on a
  verified, hash-bound, human-attested approval, and never auto-resolves.
- The floor-override fixture (AI9) passes: a claim's `min_governor_tier`
  holds regardless of a weaker suite-wide default.
- The unified `challenge_event` schema (AI8) is the only shape written —
  no parallel reversal/veto structures survive in code.
- The mechanical governor tier is on by default in a fresh suite (AI10);
  no configuration step is required to get it.

## 9 · Relationship to the other plans

This is the infrastructure `oracle-strength-and-decorrelation.md` assumed
— that PRD specifies *what* R2 (adversary) and R5 (governor) must
guarantee (isolation, verified identity, capture-rule integration); this
PRD specifies *how* recurve is shaped so those guarantees are structural
rather than per-feature bespoke code, and so the *next* ablation switch
(a `kernel_verified` governor adapter, a differential-mechanical
reference generator, whatever `eval-full.md`'s program surfaces next) is
a new adapter file, not a new architecture.

It also borrows rather than reinvents, more completely than first
scoped: `auths-curve`'s already-shipped signer/witness seam (§5a)
supplies the cryptographic backbone for AI6's human sign-off and AI7's
provenance upgrade — the same mechanism that signs recurve's own gate
verdicts today, repointed at governor approvals — and the sibling
`auths` repo's `auths-core` storage backends
(`secure_enclave.rs`/`macos_keychain.rs`/`ios_keychain.rs`/
`android_keystore.rs`) already provide the Touch-ID/Secure-Enclave-gated
key storage AI6 needs for `mint_human`, verified directly against source
rather than assumed. There is no genuinely new piece here — this PRD's
job is wiring three already-shipped mechanisms (agent/witness signing,
biometric key storage, and the recurve gate) together, not building any
of them from scratch.

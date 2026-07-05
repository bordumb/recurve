# ablation — ports, adapters, and isolation for adversary/governor, probed

> `docs/plans/ablation-infra.md`: the *how* to `oracle-strength-and-decorrelation.md`'s
> R2 (cross-model adversary) and R5 (the governor). Ports (`Adversary`/
> `Governor`) live beside `World`/`Actor` in `recurvelib.loop`; concrete
> adapters live in a new `recurvelib.adapters` package so adding switch N+1 is
> a new file plus one registry line, never a change to the loop/controller.

## Conventions

`missing-surface` claims about `recurvelib.loop.reviewers` and
`recurvelib.adapters`, `reads: none`. Probes build real temp git repos for
snapshot/isolation claims (mirroring the `adapters` suite's own convention for
`recurvelib.loop.adapters`) and construct real dataclasses/registries
directly for the pure-Python pieces.

## AB-1 — the two ports exist; nothing existing changes

`Adversary`/`Governor` protocols (`recurvelib.loop.reviewers`) are added;
`World`, `Actor`, `capture()`, `within_boundary()`, `guarded_propose()`
(`recurvelib.loop.runtime`) are untouched. Neither verdict type
(`AdversaryVerdict`/`GovernorVerdict`) can certify a claim GREEN directly —
both are structurally checked (`has_bypass_field`) to carry no
certification-shaped field; proposing is the only power either port has, and
`capture()` still independently judges any proposed trap.

Negative space: a capture-rule regression (any of the four canonical
`capture(bool, bool)` truth-table cells disagreeing with the spec) must turn
the probe RED. A verdict type carrying a bypass-shaped field (`certified`,
`closed`, `green`, ...) must be flagged by `has_bypass_field`, not silently
accepted.

## AB-2 — context snapshots enforce the exclusion boundary mechanically

`ClaimSnapshot`/`CycleSnapshot` (`recurvelib.adapters.snapshot`) are built
only from `git archive <pinned-commit>`, extracted into a fresh temp
directory. A dirty working tree is refused by default
(`require_clean=True`); even bypassing that refusal, the archive never
contains an uncommitted change — `git archive`'s own guarantee, defense in
depth beside the explicit check. `include_existing_traps` (default `False`
for a claim snapshot, `True` for a cycle snapshot) strips or keeps the
gap's own trap fixtures from the extracted tree.

Negative space: a snapshot builder that silently accepts a dirty tree, or
that leaks existing traps into a snapshot built with
`include_existing_traps=False`, must turn the probe RED.

## AB-3 — isolation strategy is pluggable and per-adapter, not global

`recurvelib.adapters.isolation` resolves `subprocess_tempdir` (default) or
`docker` (opt-in) per adapter. `subprocess_tempdir.run_isolated` pins the
child's cwd to the snapshot root and hands it a scrubbed environment — only
a narrow allowlist of prefixes (PATH, provider credentials) survives from the
caller's own process; no acting-agent session variable rides along.
`docker.run_isolated` mounts the snapshot read-only into a container,
selected only when an adapter declares a heavy-runtime need.

Negative space: an isolation invocation that hands the child the parent's
full, unscrubbed environment must turn the probe RED.

## AB-4 — shared reviewer plumbing, written once

`recurvelib.adapters._shared.reviewer_base.run_claim_reviewer`/
`run_cycle_reviewer` compose snapshot construction, isolated invocation, and
provenance attachment in one call — the code path every `adversary/*.py`/
`governor/*.py` adapter uses, rather than each reimplementing its own copy.
A lint-shaped check (`adapters_not_using_shared`, nice-to-have, not a hard
release gate) flags an adapter file that rolls its own `subprocess`
invocation instead of importing this module.

Negative space: an adapter file that reimplements subprocess plumbing
directly, with no import of `_shared.reviewer_base`, must be flagged.

## AB-5 — uniform provenance: every port, two tiers of strength

`recurvelib.adapters._shared.provenance.Provenance` closes the asymmetry
where R2/R5 verify the adversary/governor's identity against the actor's
but never held the actor's own identity to the same standard —
`metadata_verified` (cheap, the served-model field) and
`cryptographically_attested` (an auths-signed envelope) are both available
to any port. `verified_different_identity` is R2/R5's identity check in one
place: true only when both sides are actually verified AND their identities
differ.

Negative space: a claimed `cryptographically_attested` provenance whose
envelope fails (or raises during) verification must demote to `unverified`
with the reason recorded, never silently accepted. Two provenances sharing
the same identity — the same-model-adversary / actor-signs-with-its-own-key
shape — must never count as verified-different.

## AB-6 — the adversary registry + off/same_model/cross_model adapters

`recurvelib.adapters.adversary.ADVERSARY_ADAPTERS` resolves `off`
(no-op, always `no_objection`), `same_model` (isolated review, no identity
requirement), and `cross_model` (isolated review + identity check) — this
satisfies R2's automated tiers. The reviewer is a BYO command (same shape as
`CommandActor`): it runs in the isolated snapshot and prints one JSON
verdict naming its own `served_model`. `cross_model` refuses — raising
`CrossModelIdentityViolation` — when its verified served identity does not
verifiably differ from the actor's, checked from the reviewer's own reported
identity, never a caller-supplied "requested" model string.

Negative space: an adapter that skips the identity check entirely, or that
verifies against a requested/self-reported model instead of the actually
served one (the config-drift shape — the flag says one thing, the server did
another), must turn the probe RED. A malformed adapter (no `.review`) must
be refused at registration, not first invocation. The isolated reviewer must
never see the acting agent's live working directory.

## AB-7 — the governor registry + off/mechanical/mechanical_review adapters

`recurvelib.adapters.governor.GOVERNOR_ADAPTERS` resolves `off` (always
cleared), `mechanical` (fresh-checkout re-execution of the cycle's
probes+traps — catches state leakage and trap-weakening, near-free, no LLM),
and `mechanical_review` (a single decorrelated-model pass over the cycle's
batch — catches correlated authorship, the O6 shape, at the run level).
`mechanical_review` reuses R2's identity machinery exactly: it refuses
(`GovernorIdentityViolation`) when its verified served identity does not
verifiably differ from the cycle's claim-authoring identity, and never
silently falls back to `AGENT_CMD` when `RECURVE_GOVERNOR_CMD` is unset.

Negative space: a mechanical governor that clears regardless of what the
fresh checkout's re-execution actually says (never catching state leakage)
must turn the probe RED. A review-tier governor that skips the identity
check, silently clearing a same-identity batch, must turn the probe RED.

## AB-8 — policy floor (AI9) + the mechanical governor default-on (AI10)

`recurve.toml` gains `[gate] adversary = off|same_model|cross_model`
(default `off`) and `[gate] governor = off|mechanical|mechanical_review|
human_required` (default `mechanical` — pre-launch, zero cost, no existing
deployment to preserve). A claim's `min_governor_tier` (`recurvelib.core.model.Gap`,
validated at parse time) floors `recurvelib.adapters.policy.effective_governor_tier`
at at least that strength, regardless of a weaker suite-wide default — never
weakening a stronger one.

Negative space: a policy resolution that lets a weaker suite-wide default
(e.g. `off`) suppress a claim's stronger floor must turn the probe RED. An
unrecognized tier name, as either the suite default or a claim's floor, must
refuse rather than resolve to something silently wrong.

## AB-9 — one challenge_event schema, not two

`recurvelib.adapters.challenge_event` unifies R4's reversal event and R5's
veto event into one `challenge_event` type, distinguished only by
`phase: pre_publication | post_publication`, always carrying the tier held
at challenge time and a required `reason` (never a bare rejection). `recurve
stats` reports the combined rate, sliceable by phase.

Negative space: an event authored in the OLD, separate reversal/veto shape
must be refused outright — there is deliberately no dual-schema
compatibility path.

## AB-10 — one registry, two consumers, no duplication

`eval/evallib/arms.py` imports `ADVERSARY_ADAPTERS`/`GOVERNOR_ADAPTERS` from
`recurvelib.adapters` rather than reimplementing them, and gains A7-A10
(`eval-full.md`'s ablation-phase arms: `A3 + adversary=cross_model`,
`A3 + governor=mechanical`, `A3 + governor=mechanical_review`, and the full
stack) — the POC's `{A0, A3}` scope is unchanged. `eval/` stays a separate
uv project (recurvelib is stdlib+PyYAML); the dependency is one-directional.

Negative space: a candidate `arms.py` that defines its own local
`ADVERSARY_ADAPTERS`/`GOVERNOR_ADAPTERS` mapping instead of importing
recurvelib's must be flagged — a lint-shaped drift check.

## AB-11 — human_required's async state machine (AI6)

`recurvelib.adapters.governor.human_required` implements R5's human tier:
with no attestation yet, `audit()` returns `pending_human_signoff` and the
loop suspends cleanly (never busy-waits). `write_attestation` (production:
`recurve governor approve`) signs `{cycle_snapshot_hash, claim_ids,
decision, rationale}` bound to the exact reviewed snapshot;
`verify_attestation` fail-closes on three checks in order: the signature
verifies, the signer is human-attested (`_shared.identity.is_human_identity`
— a POSITIVE capability, never the mere absence of an agent one), and the
signed hash matches the CURRENT snapshot (replay/drift). A present-but-
invalid attestation stays pending — never auto-resolves to cleared or veto.

Proven with a real Ed25519 keypair and real signatures (the `cryptography`
package) standing in for `auths-core`'s Secure-Enclave-gated key — mocked
ONLY where the key lives; the signature/verification machinery and the
identity-type discrimination are genuine, not simulated.

Negative space: an attestation whose signed hash no longer matches the
current snapshot (replay/drift), or one signed by an agent-attested
identity, must be refused — stays pending, never clears.

## AB-12 — the real Secure-Enclave production seam exists (honest limit)

Verifies, structurally, that `auths-core`'s real biometric-gated backend
(`crates/auths-core/src/storage/secure_enclave.rs`: Touch-ID/Face-ID gated
signing, a biometric-cancellation error path, a hardware-availability
check) and the real `auths` CLI's `sign`/`init` entrypoints exist and match
AI6/§5a's design — verified against source, not assumed. Then honestly
SKIPs: a live biometric consent event cannot be exercised by this
unattended, autonomous process, and this probe does not attempt to trigger
a real Touch ID prompt. Declared via `oracle_waiver`, not laundered as
tested. AB-11 proves everything up to this exact boundary for real.

Negative space: a sabotaged sibling `auths` tree missing the documented
biometric-gate markers must be rejected by the structural checks before the
probe ever reaches its SKIP.

## AB-13 — [gate] governor= is invokable via config alone (the live wiring)

`recurve decide` (`recurvelib.analysis.decide_cli.verdict_for_configured`),
when a config resolves and the gate/mechanical vector is green, resolves
`[gate] governor=` through the SAME registry AB-6/AB-7 built, invokes the
real adapter against the ledger's currently-closed claims, and feeds its
verdict into `decide()` — the exact call
`templates/workflows/burndown.sh`'s `stop_verdict()` already makes
(`$PROG decide --open ... --regressed ... --broken ... --uncovered ...`),
completely unchanged. Proven with real `recurve decide` subprocess
invocations over a tiny fixture project (`governor = "mechanical_review"`),
including sourcing the REAL, unmodified shipped `stop_verdict()` bash
function directly. `governor = "off"` (the sibling fixture) is byte-for-byte
unaffected.

Negative space: `governor=mechanical_review` configured with no
`RECURVE_GOVERNOR_CMD` wired must never reach `STOP-SUCCESS` — a governor
that cannot be consulted must resolve to `pending` (`PENDING-GOVERNOR`),
never silently to `cleared`.

## AB-14 — a real `drill --diff` disagreement records a challenge_event

`drill --diff` finding a disagreement on a CLOSED claim's CURRENT state — a
genuine finding, not a self-test replay of a known fixture — is exactly R4/
AI8's named "later differential pass" trigger. `_record_diff_challenge`
(`recurvelib/cli/commands/drill.py`) records a real `challenge_event`
(`phase="post_publication"`, a derived tier, a concrete reason) via
`recurvelib.adapters.challenge_event.ChallengeLog` — append-only, and it
surfaces in `recurve stats`'s challenge-rate line, which now reports
regardless of whether any run record exists yet (a ledger-derived rate, not
a run-record-derived one).

Negative space: a `drill --diff` disagreement on a closed claim that leaves
no trace at all (the one-line recording call removed) must turn the probe
RED.

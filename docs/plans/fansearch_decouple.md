# PRD — fansearch: decoupling the discovery engine from any one target

> Supersedes the previous version of this document. That version's vision
> (a proxy-guides/gate-decides discovery loop, F0–F8) stands; this version
> corrects an architecture drift that showed up during a real
> implementation pass — the "domain-agnostic campaign engine" the original
> document specified in words ended up, in code, hardcoding one target's
> language and file layout. This document exists to name that failure
> mode precisely and specify the interface that prevents it.

## 0 · What went wrong, concretely

`recurve` is a general claims-driven tool: point it at any project's
`recurve.toml` and it turns documented claims into probed, gated,
burned-down gaps. Nothing about `recurvelib`'s core is supposed to know
what language a target project is written in, let alone which one.

Building the `dyadic_lyapunov` POC against the sibling `navier_stokes`
repo (a Lean project), the following landed in what was supposed to be
`recurve`'s domain-agnostic engine:

- `recurvelib/fansearch/campaign.py::verify_compiled_claim` — hardcodes
  `import NavierStokes.Shells.Basic`, `namespace NavierStokes.Shells`,
  and invokes `lake env lean` directly.
- `recurvelib/fansearch/promote.py::promote_candidate` — hardcodes the
  path `NavierStokes/Shells/Basic.lean`, the literal marker
  `end NavierStokes.Shells`, the suite name `"shells"`, a
  `_DEFINITION_PINS` block of Lean text copy-pasted from that repo's
  actual definitions, and shells out to `lake build` and
  `recurve baseline shells` by name.
- The parameter name `ns_repo` threaded through both files and the CLI
  (`recurve fansearch run --ns-repo`, `--claim-id`) bakes in "the target
  is `navier_stokes`" as a naming assumption, not just a value.

None of this is domain adapter code (which is *allowed* to know its
subject matter deeply — `dyadic_lyapunov.py`'s shell-model math is
exactly where that belongs). This is engine code: the part every future
domain and every future target project routes through. As written, it
cannot verify or promote a claim into anything that isn't this one Lean
repo with this one file layout. A second domain adapter targeting, say,
a Python project with pytest-checked claims would need its own copy of
`campaign.py`/`promote.py` — exactly the duplication `recurve`'s whole
adapter-registry discipline (`recurvelib/adapters/registry.py`) exists to
prevent everywhere else.

The root cause: `recurve` already has the right abstraction for "a
secondary tree, in some other repo, with its own rebuild and gate
commands" — `[sculpts.<name>]` (`recurvelib/core/config.py::SculptConfig`:
`tree`, `rebuild`, `gate`, fully config-driven, already used elsewhere in
this codebase for exactly this purpose). The campaign/promote code never
used it. It reinvented a bespoke, Lean-shaped path instead.

## 1 · The fix, in one sentence

**The engine (`recurvelib/fansearch/*`) may know about candidates, proxy
scores, archives, budgets, and *the domain adapter's own interface* — and
nothing else.** Every fact about a target's language, toolchain, file
layout, or build/gate command lives in exactly one of two places: the
sculpt config (repo-level: where the tree is, how to rebuild it, how to
gate it — all shell commands, all data, zero code) or the domain adapter
(claim-shape-level: how a candidate becomes a written artifact in *that
target's* convention — real code, but scoped to the adapter, never the
engine).

## 2 · The corrected interfaces

### 2.1 `ClaimDraft` stays a pure data value, but stops assuming Lean

Today's `ClaimDraft` (`recurvelib/adapters/proxy/compile_to_claim.py`) is
already the right shape in spirit — `compile_to_claim(candidate) ->
ClaimDraft` is a pure function, no disk writes, no gate calls. What it
returns (`theorem_lean`, `statement_lean`, `trap_lean`) is fine to be
Lean-flavored text *for a Lean-checked domain* — a domain targeting a
Python-tested project would return Python text instead. The problem was
never that the adapter knows about Lean; it's that the *engine* also
learned Lean by reading the adapter's field names and hardcoding how to
assemble and place them. Fix: the adapter, not the engine, owns assembly
and placement.

### 2.2 Two new adapter-supplied functions replace the engine's hardcoded logic

Alongside `propose_candidate` and `compile_to_claim`, a domain adapter
that supports automated promotion now also supplies:

```python
def verify_in_target(draft: ClaimDraft, target_tree: Path, timeout_s: int) -> tuple[bool, str]:
    """Read-only: does this draft actually hold against the target tree,
    without writing anything there? Returns (ok, detail). The engine
    calls this to decide whether a new record counts as gate-confirmed;
    it never inspects `draft`'s fields itself."""

def write_into_target(draft: ClaimDraft, target_tree: Path, claim_id: str) -> list[Path]:
    """Write this draft into the target tree's own ledger, in whatever
    files and format that target's own claim convention expects (a new
    Lean theorem + check/trap/probe triple + a gaps.draft.yaml entry, for
    a Lean-checked target; a new pytest module + fixture, for a
    Python-checked one). Returns the paths written. Never rebuilds, never
    gates, never commits -- the engine does those next, generically."""
```

Both live beside `compile_to_claim` in the domain adapter's own module
(`dyadic_lyapunov.py`, resolved the same way `propose_candidate` already
is: `sys.modules[cls.__module__]`). `dyadic_lyapunov`'s versions are where
`NavierStokes/Shells/Basic.lean`, `end NavierStokes.Shells`, and the
definition-pin text move *to* — they are exactly as Lean-specific as
they are today, just relocated from the engine into the one place that's
supposed to hold target-shape knowledge.

### 2.3 Rebuild and gate go through `[sculpts.<name>]`, not a shelled-out literal

`recurvelib/fansearch/promote.py` currently does:

```python
subprocess.run(["lake", "build", "NavierStokes"], cwd=ns_repo, ...)
subprocess.run(["recurve", "baseline", "shells"], cwd=ns_repo, ...)
```

Both commands are already exactly the shape `SculptConfig.rebuild` and
`SculptConfig.gate` exist for. The corrected engine reads them from
config instead:

```toml
# recurve.toml, in the repo running the campaign
[sculpts.dyadic_lyapunov_target]
tree = "../navier_stokes"
kind = "lean"                              # advisory only
rebuild = "lake build NavierStokes"
gate = "recurve baseline shells"
```

```python
sculpt = cfg.sculpts[args.target]           # not "ns_repo": a configured sculpt name
subprocess.run(shlex.split(sculpt.rebuild), cwd=sculpt.tree, ...)
subprocess.run(shlex.split(sculpt.gate), cwd=sculpt.tree, ...)
```

The engine now contains zero characters of `lake`, `lean`, or
`NavierStokes` — that knowledge lives entirely in one `recurve.toml`
stanza, authored once per project that wants to run a campaign against a
particular target. Pointing the exact same engine at a *different* kind
of target is a config edit, not a code change.

### 2.4 Naming: `ns_repo` becomes `target` (a sculpt name), everywhere

`--ns-repo <path>` (a raw filesystem path, Lean-shaped in spirit even
where the type signature doesn't say so) becomes `--target <sculpt-name>`
(a name resolved through `cfg.sculpts`, the same way every other
cross-repo reference in this codebase already resolves). This alone
removes the "obviously this tool assumes Lean" smell even before reading
a line of the implementation.

## 3 · What stays exactly as it is

- `recurvelib/core/protocols.py` (`ProxyEvaluator`, `ProxyScore`) — already
  fully domain-agnostic; nothing to change.
- `recurvelib/adapters/registry.py` (`build_registry`/`resolve`) — already
  fully generic; nothing to change.
- `recurvelib/fansearch/campaign.py`'s archive format, budget, and
  dry-generations stop — these are about the search's own bookkeeping,
  never about any target's shape. Unchanged, except `verify_compiled_claim`
  is deleted from this file and its logic moves into the domain adapter
  as `verify_in_target` (§2.2), and the engine's own call site becomes a
  generic dispatch to whichever adapter is registered.
- `dyadic_lyapunov.py`'s math (`Candidate`, `dphi_dt`, `DyadicLyapunovProxy`,
  `propose_candidate`) — already has zero target-repo knowledge. Unchanged.
- `compile_to_claim.py`'s text-generation logic — unchanged in substance;
  `verify_in_target`/`write_into_target` are new functions that consume its
  output, not replacements for it.

## 4 · Proving the decoupling actually happened

A refactor that claims "the engine is domain-agnostic" is exactly the
kind of claim this whole tool exists to stop people from asserting on
vibes. The test is not "does `dyadic_lyapunov` still work" (it would,
even with zero decoupling, since it's the only domain that exists). The
test is:

- **A second, deliberately different domain adapter** — one whose target
  is *not* Lean at all (a plain Python project with pytest-checked
  claims is the cheapest genuine proof: `verify_in_target` runs `pytest`
  against a scratch copy, `write_into_target` writes a new test module
  plus a `gaps.draft.yaml` entry, `[sculpts.*].rebuild` is empty,
  `.gate` is `pytest -q`). It does not need to be mathematically
  interesting — its only job is to exist without a single new line in
  `recurvelib/fansearch/*`.
- **A grep, not a vibe**: `grep -rn "lake\|lean\|NavierStokes" recurvelib/fansearch/`
  returns nothing. This is the actual, mechanical acceptance criterion —
  add it as a claim's probe (`class: missing-surface`, a real regression
  guard) once the refactor lands, exactly the same discipline every other
  "no fourth hand-copy" guard in this codebase already uses.

## 5 · Migration order

1. Add `verify_in_target`/`write_into_target` to `dyadic_lyapunov.py`,
   moving the Lean-specific bodies over from `campaign.py`/`promote.py`
   verbatim first (a pure relocation, behavior-preserving, checked against
   the existing `SHX1`-style real promotion before anything else changes).
2. Rewrite `campaign.py`'s verify call site and `promote.py`'s write/
   rebuild/gate call sites to dispatch through the adapter + sculpt config
   generically. Delete the hardcoded strings from both files.
3. Rename `ns_repo`/`--ns-repo` to `target`/`--target` throughout the CLI,
   engine, and existing claims' probes.
4. Add the second (non-Lean) domain adapter from §4 and the grep-based
   regression guard.
5. Only then resume F7/F8/second-adapter work under the old plan's
   remaining scope — on the corrected architecture, so nothing further
   gets built against the coupled shape.

## 6 · What this does not change

The rest of the original plan's content — F0's validation stages, F1's
`ProxyEvaluator`/registry seam, F5's `dyadic_lyapunov` math, F6's
anti-reward-hack discipline, F7's receipt provenance, F8's budget/dry-
generations stop — is unaffected in substance. Every one of those was
already correctly domain-agnostic or correctly domain-scoped; only the
plumbing connecting a domain adapter's output to a specific target
repo's build/gate/file-layout leaked target-specific knowledge into the
wrong layer. This document's only job is to put that knowledge back
where it belongs before more is built on top of it.

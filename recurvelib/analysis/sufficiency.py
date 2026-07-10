"""Sufficiency: the mechanically-checkable half of "is this the right cut?"

`docs/plans/autonomous_solver.md` §1 splits "is this decomposition right" into
two questions, exactly one of which has an arbiter:

  - Sufficiency (ARBITERED, this module): do the leaves imply the goal? Author
    the ASSEMBLY claim — a single theorem that proves the goal FROM the leaves
    taken as HYPOTHESES — and gate it exactly like any other claim, through
    the same `run_baseline` / `run_matrix` path everything else goes through.
    GREEN + kernel-clean means "L1 ∧ ... ∧ Ln ⟹ goal" is a kernel-verified
    fact; **a cut is accepted exactly when its assembly goes GREEN**. No new
    arbiter, no self-grading.
  - Provability & taste (UN-ARBITERED): are the leaves themselves true? Is the
    cut sensible? No oracle here — adjudicated later by the loop trying to
    close each leaf (a false leaf fails and parks) and, at the boundary, by a
    human. This module does not touch that question.

Two guards make a WRONG cut harmless without any new trust: a bad **cut**
fails `sufficiency_ok` (the assembly comes back RED or BROKEN); a bad **leaf**
is caught RED-first at its own arming (`run_baseline` promotes a GREEN leaf to
`closed` only after its trap was seen RED — see `core/baseline.py`), so a
leaf cannot be vacuously true.

## Why the assembly is a standalone theorem, not a splice into real source

The assembly is NOT a permanent addition to the target's codebase — it is a
throwaway mechanical certificate ("assuming these leaves, does the goal
follow?"). `write_lean_assembly_scaffold` therefore writes it to its OWN,
otherwise-untouched Lean file under the target tree (never splicing into an
existing module), and the accompanying `.check.lean` PINS that theorem by
name (`example (h1 : L1) ... : goal := <name> h1 ...`) rather than defining it
inline — this is what lets the shared `_lean_probe.sh` engine's trap
mechanism work unmodified: a trap fixture redefines `<name>` with `sorry`
standalone, and the check file (its own `import` lines stripped) is appended
after it, so the trap's sorried definition — not a second, conflicting
definition — is what the pin resolves against. Get this composition wrong (define
the theorem inline in the check file) and the trap-composed file fails to
elaborate at all (`<name>` declared twice), which would misreport as BROKEN,
not RED — silently defeating the one check this module exists to provide.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Callable

from recurvelib.core.baseline import BaselineOutcome, run_baseline
from recurvelib.core.conformance import Matrix, run_matrix
from recurvelib.core.config import Config
from recurvelib.core.model import Gap, Status, load_ledger
from recurvelib.core.probe import Outcome, ShellProbeRunner, run_traps


@dataclass(frozen=True)
class Leaf:
    """One child obligation of a decomposition — a hypothesis the assembly
    may assume true. `id` need not yet exist as an armed `Gap` (a leaf can be
    proposed before it is itself proved) — sufficiency only asks whether
    ASSUMING it, the goal follows; whether the leaf itself closes is a
    separate, later question this module does not answer."""

    id: str
    statement: str            # the leaf's proposition, as a Lean type
    hypothesis_name: str      # the name the assembly binds it to (e.g. "hL1")


@dataclass(frozen=True)
class Cut:
    """A proposed decomposition of `parent_id : goal_statement` into `leaves`,
    with `assembly_proof` the tactic script deriving the goal from the leaves
    (each leaf in scope under its `hypothesis_name`). Everything the goal and
    leaf statements reference — types, opens, ambient `variable`s — must be
    supplied explicitly (`imports`/`opens`/`variables`); the assembly is
    otherwise self-contained (see module docstring for why it doesn't read or
    write any real theorem in the target's source tree)."""

    parent_id: str
    goal_statement: str
    leaves: tuple[Leaf, ...]
    assembly_proof: str
    suite: str
    lean_module: str                    # dotted import path, e.g. "NavierStokes.Sufficiency.SubProdAssembly"
    imports: tuple[str, ...] = ()       # extra imports the STATEMENTS need, beyond `import Mathlib`
    opens: tuple[str, ...] = ()
    variables: tuple[str, ...] = ()     # raw `variable ...` lines (ambient types the statements close over)
    explicit_args: tuple[str, ...] = ()
    # Names, in declaration order, of any EXPLICIT (round-paren) `variable`s
    # named above — e.g. ("a", "b") for `variable (a b : E → ℂ)`. Lean
    # auto-generalizes a `variable` into any declaration that mentions it
    # free, inserting it as a LEADING explicit parameter — the real theorem
    # module and the check's `example` each do this independently (they're
    # separate files), so the pin's call must pass these by name before the
    # hypothesis args or Lean reports a type mismatch (it'll try to unify an
    # `hEnorm`-shaped argument against the `E → ℂ` slot `a` occupies). Purely
    # `{}`/`[]` (implicit/instance) variables need no entry here — Lean infers
    # those at the call site regardless.
    assembly_id: str = ""               # defaults to "<parent_id>-ASSEMBLY"

    def __post_init__(self) -> None:
        if not self.assembly_id:
            object.__setattr__(self, "assembly_id", f"{self.parent_id}-ASSEMBLY")

    @property
    def theorem_name(self) -> str:
        """A valid, collision-resistant Lean identifier derived from
        `assembly_id` (e.g. "SUB-PROD-ASSEMBLY" -> "sub_prod_assembly")."""
        return _slug(self.assembly_id, sep="_").lower()


@dataclass(frozen=True)
class SufficiencyResult:
    ok: bool
    detail: str
    baseline_outcomes: tuple[BaselineOutcome, ...] = ()
    matrix: Matrix | None = None


def _slug(text: str, sep: str = "-") -> str:
    """Filesystem/identifier-safe slug: keep alnum runs, join with `sep`,
    ensure the result doesn't start with a digit (a bare id like "3-FOO"
    would otherwise produce an illegal Lean identifier / awkward filename)."""
    parts = [p for p in re.split(r"[^0-9A-Za-z]+", text) if p]
    slug = sep.join(parts) or "cut"
    if slug[0].isdigit():
        slug = f"c{sep}{slug}"
    return slug


def _hypotheses_block(cut: Cut, indent: str = "    ") -> str:
    return "".join(f"\n{indent}({leaf.hypothesis_name} : {leaf.statement})" for leaf in cut.leaves)


def _preamble(cut: Cut, *, include_target_import: bool) -> str:
    imports = ["import Mathlib", *(cut.imports if include_target_import else [])]
    lines = [f"import {m}" if not m.startswith("import ") else m for m in imports]
    if cut.opens:
        lines.append("open " + " ".join(cut.opens))
    lines.extend(cut.variables)
    return "\n".join(lines)


def _theorem_source(cut: Cut, proof: str) -> str:
    """The assembly theorem's own module — a fresh file, never a splice into
    existing source. Used for the REAL (non-trap) definition."""
    return (
        f"{_preamble(cut, include_target_import=True)}\n\n"
        f"-- Sufficiency certificate for cutting {cut.parent_id} "
        f"(docs/plans/autonomous_solver.md §1.2).\n"
        f"-- Leaves are HYPOTHESES; this theorem derives the goal FROM them —\n"
        f"-- it is not a claim that the leaves themselves are true.\n"
        f"theorem {cut.theorem_name}{_hypotheses_block(cut)} :\n"
        f"    {cut.goal_statement} := by\n"
        f"  {proof}\n"
    )


def _check_source(cut: Cut) -> str:
    """The check file: a STATEMENT PIN (`example := name args`), never an
    inline definition — see module docstring for why this matters for traps.
    The call passes `cut.explicit_args` before the hypothesis names (see the
    field's docstring on `Cut`) — both this `example` and the real theorem
    independently auto-generalize any EXPLICIT `variable` they mention free,
    as a leading parameter, so the pin must supply it by name too."""
    args = " ".join((*cut.explicit_args, *(leaf.hypothesis_name for leaf in cut.leaves)))
    return (
        f"import {cut.lean_module}\n\n"
        f"{_preamble(cut, include_target_import=False)}\n\n"
        f"-- statement pin: {cut.assembly_id} — does the cut of {cut.parent_id} imply the goal?\n"
        f"-- Pins `{cut.theorem_name}` kernel-clean (a dodged `sorry` is caught by #print axioms).\n"
        f"example{_hypotheses_block(cut)} :\n"
        f"    {cut.goal_statement} :=\n"
        f"  {cut.theorem_name} {args}\n\n"
        f"#print axioms {cut.theorem_name}\n"
    )


def _trap_source(cut: Cut) -> str:
    """The sorried counterexample: SAME preamble (including `cut.imports`,
    for the ambient types the statement references — e.g. definitions like
    `weightFun` this cut's leaves/goal are stated over) and the SAME theorem
    NAME/SIGNATURE as the real module, but a dodged proof. It does NOT import
    `cut.lean_module` itself (the assembly's own new file) — that import is
    what the check file supplies, and gets stripped for the trap run
    (`_lean_probe.sh`'s `grep -v '^import '`), so this fixture's sorried
    definition is the only one of `theorem_name` left standing once the
    check's (import-stripped) tail — including its `#print axioms` line — is
    appended after it."""
    return (
        f"{_preamble(cut, include_target_import=True)}\n\n"
        f"-- KNOWN-BAD: the exact {cut.assembly_id} statement, but the derivation is dodged.\n"
        f"-- The probe must catch this via the `#print axioms` sorryAx report.\n"
        f"theorem {cut.theorem_name}{_hypotheses_block(cut)} :\n"
        f"    {cut.goal_statement} := by\n"
        f"  sorry\n"
    )


def _draft_entry_yaml(cut: Cut) -> str:
    import yaml

    entry = {
        "id": cut.assembly_id,
        "title": f"sufficiency certificate: does the cut of {cut.parent_id} imply the goal?",
        "class": "missing-surface",
        "severity": "feature",
        "reads": "none",
    }
    # A cut whose assembly_id is deliberately overridden to equal its own parent_id
    # (recurvelib.loop.solver's root-completion: the FINAL, unconditional proof of a
    # decomposition's own root, once every leaf has closed) has no DAG parent above it
    # — covers_claim would otherwise be a self-reference, which Gap.parse rejects.
    if cut.parent_id != cut.assembly_id:
        entry["covers_claim"] = [cut.parent_id]
    entry.update({
        "evidence": [f"probes/{_slug(cut.assembly_id)}.sh:1"],
        "smallest_fix": (
            f"Prove {cut.theorem_name} (statement pin of probes/{_slug(cut.assembly_id)}.sh): "
            f"from the leaves {', '.join(l.id for l in cut.leaves)} as hypotheses, derive the goal. "
            f"Autogenerated by recurvelib.analysis.sufficiency.write_lean_assembly_scaffold."
        ),
        "probe": f"probes/{_slug(cut.assembly_id)}.sh",
        "unlocks": f"discharges {cut.parent_id} once every leaf above also closes",
    })
    return yaml.safe_dump([entry], sort_keys=False, allow_unicode=True, width=88)


def _assert_no_probe_collision(cut: Cut, config: Config, slug: str) -> None:
    """Refuse to write scaffold files that would silently clobber a DIFFERENT
    claim's real probe/check/trap — a real risk discovered empirically: on the
    case-insensitive-but-preserving filesystem this project actually runs on
    (macOS/Windows default), `_slug`'s case-PRESERVING output (it does not
    lowercase) can resolve to the SAME on-disk path as an existing claim's
    differently-cased slug, so writing `cut`'s scaffold there overwrites that
    claim's real files. Checked case-insensitively regardless of the actual
    filesystem, so the guard is uniform rather than a platform-dependent trap.

    Writing over `cut.assembly_id`'s OWN existing files (re-deriving or
    re-checking the SAME claim — see `sufficiency_ok`'s promotion path for an
    already-ledgered gap) is fine and not flagged; only a collision with SOME
    OTHER claim's probe path is refused."""
    ledger = load_ledger(config)
    sc = config.suite_for(cut.suite)
    target = str((sc.dir / "probes" / f"{slug}.sh").resolve()).lower()
    for g in ledger.gaps:
        if g.id == cut.assembly_id or g.probe is None:
            continue
        if str(g.probe.resolve()).lower() == target:
            raise ValueError(
                f"refusing to write scaffold files for assembly_id={cut.assembly_id!r} — its "
                f"probe path collides (case-insensitively) with existing claim {g.id!r}'s own "
                f"probe ({g.probe}). Choose a different assembly_id, or if you intend to "
                f"re-derive {g.id!r} itself, set assembly_id={g.id!r} exactly."
            )


def write_lean_assembly_scaffold(cut: Cut, config: Config, build_timeout_s: int = 300) -> None:
    """Materialize `cut` as a real, gateable Lean claim: the theorem module,
    the check/probe/trap triple, and (if not already in the ledger or draft)
    a `gaps.draft.yaml` entry. Idempotent — safe to call again after editing
    `cut.assembly_proof` to iterate on a derivation; it will not duplicate the
    draft entry once the id has reached `gaps.yaml`.

    Unlike every other claim in the fleet, the assembly's module has no
    suite-level `rebuild` command covering it (a suite's `rebuild` targets its
    OWN established sources, not a scratch file this call is the first to
    create) — `import` in Lean resolves against BUILT `.olean` artifacts, not
    source, so this function builds its own new module before returning.
    `lake build` failing here (a syntax error, or — expected during real
    iteration — a proof that doesn't yet close) is not raised: the probe run
    right after this surfaces it as BROKEN/RED with a proper message; a
    `lake` binary genuinely missing from PATH is the one thing this DOES
    raise, since every subsequent step would otherwise fail opaquely."""
    sc = config.suite_for(cut.suite)
    if config.tree is None:
        raise ValueError(f"{config.name}: [target] tree does not resolve to a directory — cannot write Lean source")

    _assert_no_probe_collision(cut, config, _slug(cut.assembly_id))

    module_path = config.tree / Path(*cut.lean_module.split(".")).with_suffix(".lean")
    module_path.parent.mkdir(parents=True, exist_ok=True)
    module_path.write_text(_theorem_source(cut, cut.assembly_proof))

    import shutil
    import subprocess

    if shutil.which("lake") is None:
        raise RuntimeError("lake not on PATH — cannot build the assembly module")
    try:
        subprocess.run(
            ["lake", "build", cut.lean_module],
            cwd=config.tree, capture_output=True, text=True, timeout=build_timeout_s,
        )
    except subprocess.TimeoutExpired:
        pass  # the probe's own timeout/staleness check reports this cleanly next

    checks_dir = sc.dir / "probes" / "checks"
    checks_dir.mkdir(parents=True, exist_ok=True)
    slug = _slug(cut.assembly_id)
    (checks_dir / f"{slug}.check.lean").write_text(_check_source(cut))

    probe_path = sc.dir / "probes" / f"{slug}.sh"
    shared = sc.dir / "probes" / "_lean_probe.sh"
    if shared.exists():
        probe_path.write_text(
            "#!/usr/bin/env bash\n"
            f"# {cut.assembly_id}: sufficiency certificate for {cut.parent_id} "
            "(docs/plans/autonomous_solver.md §1.2) — delegates to the shared Lean probe engine.\n"
            f'exec "$(dirname "${{BASH_SOURCE[0]}}")/_lean_probe.sh" {slug}\n'
        )
    else:
        probe_path.write_text(_standalone_lean_probe(slug))
    probe_path.chmod(0o755)

    trap_dir = sc.dir / "probes" / f"{slug}.trap" / "sorried"
    trap_dir.mkdir(parents=True, exist_ok=True)
    (trap_dir / "Module.lean").write_text(_trap_source(cut))

    _append_draft_if_new(cut, sc.dir)


def _standalone_lean_probe(slug: str) -> str:
    """Fallback probe body for a suite with no shared `_lean_probe.sh` yet —
    the same GREEN/RED/BROKEN contract, self-contained (no staleness guard;
    a suite this bare has no established artifact-freshness convention to
    reuse, so it always rebuilds fresh via `lake env lean`)."""
    return (
        "#!/usr/bin/env bash\n"
        f"# {slug}: standalone sufficiency probe (no shared _lean_probe.sh found in this suite).\n"
        "set -u\n"
        'DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"\n'
        'ROOT="$(cd "$DIR/../../../.." && pwd)"\n'
        f'CHECK="$DIR/checks/{slug}.check.lean"\n'
        'command -v lake >/dev/null 2>&1 || { echo "lake not on PATH"; exit 2; }\n'
        'TMPD="$(mktemp -d)" || { echo "mktemp failed"; exit 2; }\n'
        "trap 'rm -rf \"$TMPD\"' EXIT\n"
        'if [ -n "${TRAP_FIXTURE:-}" ]; then\n'
        '  FIX="$TRAP_FIXTURE/Module.lean"\n'
        '  [ -f "$FIX" ] || { echo "trap fixture without Module.lean"; exit 2; }\n'
        '  { cat "$FIX"; printf \'\\n\'; grep -v \'^import \' "$CHECK"; } > "$TMPD/Check.lean"\n'
        "else\n"
        '  cp "$CHECK" "$TMPD/Check.lean"\n'
        "fi\n"
        'OUT="$(cd "$ROOT" && lake env lean "$TMPD/Check.lean" 2>&1)"\n'
        "STATUS=$?\n"
        'if [ $STATUS -ne 0 ]; then\n'
        '  FIRST_ERR="$(printf \'%s\\n\' "$OUT" | grep -m1 -i \'error\' | cut -c1-140)"\n'
        '  echo "ours=pin failed to elaborate: ${FIRST_ERR:-unknown error} oracle=pinned statement elaborates cleanly"\n'
        "  exit 1\n"
        "fi\n"
        'FLAT="$(printf \'%s\' "$OUT" | tr \'\\n\' \' \')"\n'
        'VIOL=""\n'
        'while IFS= read -r grp; do\n'
        '  axlist="${grp#depends on axioms: [}"; axlist="${axlist%]}"\n'
        '  IFS=\',\' read -r -a axs <<< "$axlist"\n'
        '  for ax in "${axs[@]}"; do\n'
        '    ax="$(printf \'%s\' "$ax" | sed \'s/^[[:space:]]*//;s/[[:space:]]*$//\')"\n'
        '    case "$ax" in propext|Classical.choice|Quot.sound|"") ;; *) VIOL="$VIOL $ax" ;; esac\n'
        "  done\n"
        'done < <(printf \'%s\' "$FLAT" | grep -o \'depends on axioms: \\[[^]]*\\]\')\n'
        'if [ -n "$VIOL" ]; then\n'
        '  echo "ours=proof depends on axioms:$VIOL oracle=kernel-clean (propext/Classical.choice/Quot.sound only; sorryAx = unproved)"\n'
        "  exit 1\n"
        "fi\n"
        'echo "pinned statement elaborates and is kernel-clean (axiom whitelist)"\n'
        "exit 0\n"
    )


def _append_draft_if_new(cut: Cut, suite_dir: Path) -> None:
    import yaml

    ledger_path = suite_dir / "gaps.yaml"
    draft_path = suite_dir / "gaps.draft.yaml"

    if ledger_path.exists():
        led = yaml.safe_load(ledger_path.read_text()) or []
        if isinstance(led, list) and any(str(e.get("id")) == cut.assembly_id for e in led if isinstance(e, dict)):
            return  # already a real ledger entry — nothing to draft

    existing_draft: list = []
    if draft_path.exists():
        existing_draft = yaml.safe_load(draft_path.read_text()) or []
        if not isinstance(existing_draft, list):
            existing_draft = []
        if any(str(e.get("id")) == cut.assembly_id for e in existing_draft if isinstance(e, dict)):
            return  # already drafted, awaiting baseline

    header = (
        "# gaps.draft.yaml — schema-shaped intentions awaiting the baseline\n"
        "# ceremony. Nothing here is an observation yet.\n"
    )
    block = yaml.safe_dump(
        [yaml.safe_load(_draft_entry_yaml(cut))[0]], sort_keys=False, allow_unicode=True, width=88
    )
    if draft_path.exists():
        draft_path.write_text(draft_path.read_text().rstrip("\n") + "\n\n" + block)
    else:
        draft_path.write_text(header + "\n" + block)


ScaffoldWriter = Callable[[Cut, Config], None]


def _promote_existing_gap(gap: Gap, config: Config, today: str, probe_detail: str) -> tuple[bool, str]:
    """Once an ALREADY-LEDGERED gap's own probe measures fresh GREEN via
    `sufficiency_ok`'s gate check, rewrite its ledger row open/sculpting ->
    closed directly. Needed because `run_baseline` only ever processes
    `gaps.draft.yaml` — a gap already in `gaps.yaml` (re-deriving or
    re-checking an EXISTING claim, not arming a fresh one) is invisible to
    it, so without this a `sufficiency_ok(..).ok == True` on such a gap would
    silently NOT update the ledger at all (discovered empirically: measured
    GREEN, `gap.status` stayed `open` on disk).

    Requires the SAME trap discipline `run_baseline`'s own GREEN-promotion
    enforces (`core/baseline.py`: "a probe never seen RED is not yet
    evidence") — this is a separate promotion path a trap-check could
    otherwise silently bypass."""
    if config.traps == "required" and not gap.trap_waiver:
        traps = run_traps(gap, ShellProbeRunner(), timeout_s=300)
        bad = [t for t in traps if not t.ok]
        if not traps:
            return False, "GREEN but unfalsified — no trap fixture, not yet evidence"
        if bad:
            return False, f"GREEN but trap {bad[0].trap} came back {bad[0].outcome.value} — {bad[0].detail[:60]}"

    import yaml

    sc = config.suite_for(gap.suite)
    ledger_path = sc.dir / "gaps.yaml"
    entries = yaml.safe_load(ledger_path.read_text()) or []
    for e in entries:
        if str(e.get("id")) == gap.id:
            e["status"] = "closed"
            e["observed"] = f"GREEN at baseline {today}: {probe_detail or '(no output)'}"
            break
    else:
        return False, f"{gap.id} vanished from the ledger mid-promotion"
    ledger_path.write_text(yaml.safe_dump(entries, sort_keys=False, allow_unicode=True, width=88))
    return True, "already-ledgered claim promoted open -> closed"


def sufficiency_ok(
    cut: Cut,
    config: Config,
    write_scaffold: ScaffoldWriter = write_lean_assembly_scaffold,
    today: str | None = None,
    timeout_s: int = 300,
) -> SufficiencyResult:
    """True iff `cut`'s assembly claim is kernel-clean GREEN — i.e. the leaves
    imply the goal. Pure reuse of the existing arming/gate path: materialize
    the scaffold, arm it RED-first (`run_baseline`), then ask the real
    arbiter (`run_matrix`, scoped to just this one claim) for a fresh
    verdict. **A cut is accepted exactly when this returns `ok=True`.**

    For a FRESH `assembly_id` (not yet in the ledger), `run_baseline` itself
    promotes open/closed via the draft ceremony — `ok=True` here already
    reflects that. For an ALREADY-LEDGERED `assembly_id` (re-deriving or
    re-checking an existing claim — `run_baseline` never touches a row
    already in `gaps.yaml`), a fresh GREEN measurement is promoted directly
    by `_promote_existing_gap`, under the same trap discipline, so `ok=True`
    always means the ledger's `status` reflects the claim, not a separate
    bookkeeping step a caller must remember to take."""
    today = today or date.today().isoformat()
    pre_existing = load_ledger(config).by_id(cut.assembly_id)
    write_scaffold(cut, config)
    outcomes, _base_ok = run_baseline(config, cut.suite, today, timeout_s=timeout_s)

    ledger = load_ledger(config)
    gap = ledger.by_id(cut.assembly_id)
    if gap is None:
        return SufficiencyResult(
            ok=False,
            detail=f"{cut.assembly_id} did not reach the ledger — see baseline outcomes",
            baseline_outcomes=tuple(outcomes),
        )

    matrix = run_matrix([gap], config, timeout_s=timeout_s)
    result = next((r for r in matrix.results if r.gap.id == cut.assembly_id), None)
    if result is None:
        return SufficiencyResult(
            ok=False,
            detail=f"{cut.assembly_id} was armed but run_matrix did not measure it",
            baseline_outcomes=tuple(outcomes),
            matrix=matrix,
        )

    green = result.outcome is Outcome.GREEN and matrix.gate_ok

    if green and pre_existing is not None and gap.status is not Status.CLOSED:
        promoted, promote_detail = _promote_existing_gap(gap, config, today, result.detail)
        return SufficiencyResult(
            ok=promoted,
            detail=f"assembly is kernel-clean GREEN — {promote_detail}",
            baseline_outcomes=tuple(outcomes),
            matrix=matrix,
        )

    if green:
        detail = "assembly is kernel-clean GREEN — the leaves imply the goal"
    else:
        detail = (
            f"assembly not sufficient: outcome={result.outcome.value} "
            f"detail={result.detail!r} gate_ok={matrix.gate_ok}"
        )
    return SufficiencyResult(ok=green, detail=detail, baseline_outcomes=tuple(outcomes), matrix=matrix)

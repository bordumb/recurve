"""recurve.toml — the project boundary.

Everything that varied between the engine's first instances, and nothing that
didn't. Suites are enumerated explicitly (never discovered by glob — a sibling
directory must not be able to pollute the ledger), freshness is a declarative
artifact→source map, and presentation details that targets inherited from
their history (what a suite is called in output, the default `reads` class)
are pinned here so output is stable and reviewable.

`load` is a total boundary function: it returns a fully-resolved Config or
raises ConfigError with a precise, file-located message. Nothing downstream
re-checks a field.
"""

from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass, field
from pathlib import Path


class ConfigError(ValueError):
    """recurve.toml could not be parsed into a valid Config."""


# Directory names never treated as source when scanning for mtimes.
_DEFAULT_SKIP_DIRS = ("target", ".git", "node_modules", "site", "docs", "examples")

# Patterns the report's honesty scan counts in ADDED diff lines — cheap tells
# that a change suppressed a check instead of meeting it.
_DEFAULT_SUPPRESSION_PATTERNS = (r"\.unwrap\(\)", r"#\[allow", r"TODO|FIXME|XXX", r"#\[ignore")


@dataclass(frozen=True)
class FreshnessRule:
    """How one `reads:` class is checked for artifact currency.

    method:
      none          — not artifact-derived; the probe guards itself.
      content-hash  — suite artifact must be byte-identical to the tree's
                      built artifact (precise; no mtime guesswork).
      mtime         — newest source mtime under `sources` must not exceed the
                      oldest artifact mtime under `artifact`.
    All path strings are kept verbatim for display; resolution happens against
    the suite dir (artifact) or the target tree (source/sources).
    """

    method: str
    artifact: str = ""
    source: str = ""
    sources: tuple[str, ...] = ()
    suffixes: tuple[str, ...] = (".rs", ".toml")
    skip_dirs: tuple[str, ...] = _DEFAULT_SKIP_DIRS
    sources_label: str = "its sources"


@dataclass(frozen=True)
class SuiteConfig:
    name: str
    dir: Path                     # absolute, resolved against the config dir
    rebuild: str = ""             # display string for stale hints (and the rebuild step)
    harness: tuple[str, ...] = ()
    reads: dict[str, FreshnessRule] = field(default_factory=dict)


@dataclass(frozen=True)
class SculptConfig:
    """A secondary tree the loop may sculpt when a claim's fix requires it
    (FR-C). The PRIMARY tree is `[target]`; each `[sculpts.<name>]` is another
    tree, in a possibly-other repo, with its OWN forbidden vocabulary, commit
    branch, freshness/rebuild command, and gate. The federated gate is green
    only when the target's probes AND every sculpt's own gate pass.

    `tree` resolves against the config root (like `[target] tree`);
    `tree_display` is what messages call it. With no `[sculpts.*]` tables the
    parser produces none of these and the Config is byte-identical to today's
    single-tree shape.
    """

    name: str
    tree: Path                    # resolved against the config root
    tree_display: str             # verbatim tree string, for messages
    kind: str = "generic"         # frontend | platform | ... (advisory taxonomy)
    branch: str = ""              # the branch a sculpt commit lands on (FR-C2)
    # FR-C4: this tree's OWN leak vocabulary, parallel to `Config.forbidden_strings`
    # for the target. Enforcement is the same as the target's: advisory in the
    # engine today (config carries it; nothing greps the tree), with the standing
    # source-grep probe per tree as the active guard (docs/plan.md §11.14). When
    # that grep becomes a built-in (a `recurve leakcheck`), it would scan THIS
    # sculpt's `tree` for THESE strings, attributing any hit to this sculpt — the
    # model already separates each tree's vocabulary so that attribution is exact.
    forbidden_strings: tuple[str, ...] = ()
    rebuild: str = ""             # how fresh artifacts reach this tree's checks
    gate: str = ""                # the sculpt's own gate command (FR-C3); empty = no gate


@dataclass(frozen=True)
class Config:
    name: str
    label: str                    # what a suite is called in human output
    root: Path                    # directory containing recurve.toml
    tree_display: str             # the [target] tree string, verbatim, for messages
    tree: Path | None             # resolved tree path (None if it doesn't exist)
    suites: dict[str, SuiteConfig]
    severity_order: tuple[str, ...]
    default_reads: str
    cycles_dir: Path
    sacred: tuple[str, ...] = ()
    forbidden_strings: tuple[str, ...] = ()
    schema_pin: str = ""          # optional major-version pin, e.g. "1"
    # [gate] traps: "required" (default) enforces the trap discipline — every
    # probe keeps a counterexample it must turn RED, waivable per-gap as
    # counted debt. "off" is for instances predating the discipline; it also
    # silences advisory validate warnings to preserve their historical output.
    traps: str = "required"
    quality: str = "pre-launch"   # the constitution preset (or a path)
    # [gate] mechanical_references: glob patterns (relative to a suite dir)
    # naming references that are mechanical ground truth (a real interpreter,
    # a fixed dataset, a golden output — no model invoked in their own
    # construction). Necessary but not sufficient for
    # `oracle_tier.is_mechanical_reference` — the reference's own source is
    # still scanned for an LLM/agent-invocation marker, so a mislabeled entry
    # here cannot buy `differential_checked_mechanical` on its own.
    mechanical_references: tuple[str, ...] = ()
    # [gate] adversary: off (default) | same_model | cross_model — R2's
    # per-claim decorrelation knob (docs/plans/oracle-strength-and-decorrelation.md).
    # Off by default: opt-in, cost-aware (the house rule — a parameter, not a
    # policy).
    gate_adversary: str = "off"
    # [gate] governor: off | mechanical (default, AI10) | mechanical_review |
    # human_required — R5's run-level knob. Pre-launch, "mechanical" is the
    # default: zero cost (re-execution of existing work, no new agent calls),
    # and there is no existing deployment whose behavior this would change.
    gate_governor: str = "mechanical"
    # [gate] boundary: enforced (default) | open — the write-boundary knob.
    # "open" is a deliberately dangerous, off-by-default engine capability:
    # reachable ONLY through this exact key/value, never a coincidence of any
    # other config path (adversary/governor typos, partial configs, another
    # arm's whole config all leave this at its default).
    gate_boundary: str = "enforced"
    # [fansearch] proxy: off (default) — the search-guide scorer a discovery
    # campaign ranks candidates with. Never trusted: it only orders the
    # queue a claim gets authored+gated from, same discipline as the other
    # adapter axes above.
    fansearch_proxy: str = "off"
    # [commit] — §11.1/§11.2: explicit, never prompting.
    commit_policy: str = "unsigned-per-cycle"   # none | unsigned-per-cycle | signed
    commit_hooks: str = "run"                   # run | gate-supersedes
    # [burndown] knob defaults for the orchestrator templates.
    burndown_cap: int = 12
    burndown_max_consecutive_failures: int = 3
    burndown_runaway_net_positive_cycles: int = 2
    # [drill] fuzz knobs — the fuzz pass is opt-in (`drill --fuzz`); these
    # bound its cost and set its failure threshold, so strictness is a budget
    # decision, never a hardcoded policy.
    drill_fuzz_n: int = 8
    drill_fuzz_fpr_max: float = 0.0
    # [drill] iso knobs — the isomorphic pass is opt-in (`drill --iso`): its
    # dual measures whether a probe's verdict HOLDS on semantics-preserving
    # variants instead of rejecting broken ones. iso_n bounds cost per probe;
    # iso_flip_max sets the failure threshold, same shape as the fuzz knobs.
    drill_iso_n: int = 8
    drill_iso_flip_max: float = 0.0
    # [receipts] signer: optional command handed each receipt's self_sha256;
    # its stdout is stored as the signature. recurve defines the receipt,
    # never the signature scheme.
    receipts_signer: str = ""
    # [receipts] verifier: the dual of signer. It receives a receipt's
    # self_sha256 on stdin and its signature as the first argument, and exits 0
    # iff the signature is valid. recurve defines the seam, never the scheme.
    receipts_verifier: str = ""
    # [gate] human_verifier: AI6's human_required governor tier verifies an
    # attestation's signature through this command (same seam shape as
    # [receipts] verifier — recurve defines the seam, never the scheme).
    # Empty means `recurve governor approve` refuses outright: an
    # attestation is never accepted without a way to verify it.
    human_verifier: str = ""
    # [report] — the deterministic run report. narrator: optional command fed
    # the rendered report + the cycle records on stdin; its stdout becomes the
    # Narrative section. recurve defines the report, never the narration.
    report_narrator: str = ""
    report_narrator_timeout: int = 120
    report_suppression_patterns: tuple[str, ...] = _DEFAULT_SUPPRESSION_PATTERNS
    report_sensitive_paths: tuple[str, ...] = ()
    # True when the config lives at <root>/.recurve/recurve.toml — the
    # contained layout, where the loop's whole footprint sits in one dotdir
    # and the target's root stays the product's own domain.
    contained: bool = False
    source_file: Path = Path("recurve.toml")
    # [sculpts.<name>] — zero-or-more secondary trees the loop may sculpt
    # (FR-C). EMPTY for a single-tree config, which keeps that config (and
    # every command's output) byte-identical to today.
    sculpts: dict = field(default_factory=dict)

    @property
    def state_dir(self) -> Path:
        return self.root / ".recurve" / "state"

    @property
    def assets_dir(self) -> Path:
        """Where init stamps loop assets (docs, claims, workflows)."""
        return self.root / ".recurve" if self.contained else self.root

    def suite_for(self, name: str) -> SuiteConfig:
        try:
            return self.suites[name]
        except KeyError:
            raise ConfigError(
                f"{self.source_file}: unknown {self.label} {name!r}; "
                f"configured: {', '.join(self.suites)}"
            )


def _rule(raw: dict, where: str) -> FreshnessRule:
    method = raw.get("method", "")
    if method not in ("none", "content-hash", "mtime"):
        raise ConfigError(f"{where}: method must be none|content-hash|mtime, got {method!r}")
    if method == "content-hash" and not (raw.get("artifact") and raw.get("source")):
        raise ConfigError(f"{where}: content-hash needs 'artifact' and 'source'")
    if method == "mtime" and not (raw.get("artifact") and raw.get("sources")):
        raise ConfigError(f"{where}: mtime needs 'artifact' and 'sources'")
    return FreshnessRule(
        method=method,
        artifact=str(raw.get("artifact", "")),
        source=str(raw.get("source", "")),
        sources=tuple(str(s) for s in raw.get("sources", [])),
        suffixes=tuple(str(s) for s in raw.get("suffixes", (".rs", ".toml"))),
        skip_dirs=tuple(str(s) for s in raw.get("skip_dirs", _DEFAULT_SKIP_DIRS)),
        sources_label=str(raw.get("sources_label", "its sources")),
    )


def load(path: Path) -> Config:
    path = path.resolve()
    try:
        doc = tomllib.loads(path.read_text())
    except (OSError, tomllib.TOMLDecodeError) as e:
        raise ConfigError(f"{path}: {e}") from e

    # Contained layout: <root>/.recurve/recurve.toml — the project root is
    # the parent of the dotdir, so `tree = "."` means the repo, never the
    # dotdir itself.
    contained = path.parent.name == ".recurve"
    root = path.parent.parent if contained else path.parent
    project = doc.get("project", {})
    target = doc.get("target", {})

    # `tree` resolves relative to the config file; `display` is what messages
    # call the tree (defaults to the tree string). The split lets a config
    # live anywhere — including outside the trees it points at — without
    # changing what operators read in freshness/stale hints.
    tree_raw = str(target.get("tree", "."))
    tree_display = str(target.get("display", tree_raw))
    tree = (root / tree_raw).resolve()
    tree_resolved: Path | None = tree if tree.is_dir() else None

    # Project-level reads rules apply to every suite; suites may override or
    # extend them. Paths in a rule are interpreted per-suite at check time.
    shared_reads = {
        key: _rule(raw, f"{path}: [reads.{key}]")
        for key, raw in (doc.get("reads") or {}).items()
    }

    suites_raw = doc.get("suites") or {}
    if not suites_raw:
        raise ConfigError(f"{path}: no [suites.*] configured — suites are explicit, never discovered")
    suites: dict[str, SuiteConfig] = {}
    for name, raw in suites_raw.items():
        reads = dict(shared_reads)
        for key, rraw in (raw.get("reads") or {}).items():
            reads[key] = _rule(rraw, f"{path}: [suites.{name}.reads.{key}]")
        suites[name] = SuiteConfig(
            name=name,
            dir=(root / str(raw.get("dir", name))).resolve(),
            rebuild=str(raw.get("rebuild", "")),
            harness=tuple(str(h) for h in raw.get("harness", [])),
            reads=reads,
        )

    triage = doc.get("triage", {})
    severity_order = tuple(
        str(s) for s in triage.get("severity_order",
                                   ["headline", "feature", "friction", "cosmetic"])
    )

    default_reads = str(project.get("default_reads", "none"))

    gate = doc.get("gate", {})
    traps = str(gate.get("traps", "required"))
    if traps not in ("required", "off"):
        raise ConfigError(f"{path}: [gate] traps must be required|off, got {traps!r}")
    mechanical_references = tuple(str(p) for p in gate.get("mechanical_references", []))
    gate_adversary = str(gate.get("adversary", "off"))
    if gate_adversary not in ("off", "same_model", "cross_model"):
        raise ConfigError(f"{path}: [gate] adversary must be off|same_model|cross_model, "
                          f"got {gate_adversary!r}")
    gate_governor = str(gate.get("governor", "mechanical"))
    if gate_governor not in ("off", "mechanical", "mechanical_review", "human_required"):
        raise ConfigError(f"{path}: [gate] governor must be "
                          f"off|mechanical|mechanical_review|human_required, got {gate_governor!r}")
    gate_boundary = str(gate.get("boundary", "enforced"))
    if gate_boundary not in ("enforced", "open"):
        raise ConfigError(f"{path}: [gate] boundary must be enforced|open, got {gate_boundary!r}")

    fansearch = doc.get("fansearch", {})
    fansearch_proxy = str(fansearch.get("proxy", "off"))
    if fansearch_proxy not in ("off",):
        raise ConfigError(f"{path}: [fansearch] proxy must be off, got {fansearch_proxy!r}")

    commit = doc.get("commit", {})
    commit_policy = str(commit.get("policy", "unsigned-per-cycle"))
    if commit_policy not in ("none", "unsigned-per-cycle", "signed"):
        raise ConfigError(f"{path}: [commit] policy must be none|unsigned-per-cycle|signed")
    commit_hooks = str(commit.get("hooks", "run"))
    if commit_hooks not in ("run", "gate-supersedes"):
        raise ConfigError(f"{path}: [commit] hooks must be run|gate-supersedes")

    burndown = doc.get("burndown", {})
    receipts = doc.get("receipts", {})
    drill = doc.get("drill", {})

    # [sculpts.<name>] — secondary trees (FR-C). No tables → empty dict →
    # byte-identical single-tree Config.
    sculpts: dict[str, SculptConfig] = {}
    for sname, sraw in (doc.get("sculpts") or {}).items():
        s_tree_raw = str(sraw.get("tree", "."))
        sculpts[sname] = SculptConfig(
            name=sname,
            tree=(root / s_tree_raw).resolve(),
            tree_display=str(sraw.get("display", s_tree_raw)),
            kind=str(sraw.get("kind", "generic")),
            branch=str(sraw.get("branch", "")),
            forbidden_strings=tuple(str(s) for s in sraw.get("forbidden_strings", [])),
            rebuild=str(sraw.get("rebuild", "")),
            gate=str(sraw.get("gate", "")),
        )

    report = doc.get("report", {})
    suppression = tuple(str(p) for p in report.get("suppression_patterns",
                                                   _DEFAULT_SUPPRESSION_PATTERNS))
    for pat in suppression:
        try:
            re.compile(pat)
        except re.error as e:
            raise ConfigError(f"{path}: [report] suppression_patterns {pat!r} "
                              f"is not a valid regex: {e}")

    return Config(
        name=str(project.get("name", root.name)),
        label=str(project.get("label", "suite")),
        root=root,
        tree_display=tree_display,
        tree=tree_resolved,
        suites=suites,
        severity_order=severity_order,
        default_reads=default_reads,
        cycles_dir=(root / str(project.get("cycles_dir", "cycles"))).resolve(),
        sacred=tuple(str(s) for s in target.get("sacred", [])),
        forbidden_strings=tuple(str(s) for s in target.get("forbidden_strings", [])),
        schema_pin=str(project.get("schema", "")),
        traps=traps,
        mechanical_references=mechanical_references,
        gate_adversary=gate_adversary,
        gate_governor=gate_governor,
        gate_boundary=gate_boundary,
        fansearch_proxy=fansearch_proxy,
        quality=str(gate.get("quality", "pre-launch")),
        commit_policy=commit_policy,
        commit_hooks=commit_hooks,
        burndown_cap=int(burndown.get("cap", 12)),
        burndown_max_consecutive_failures=int(burndown.get("max_consecutive_failures", 3)),
        burndown_runaway_net_positive_cycles=int(burndown.get("runaway_net_positive_cycles", 2)),
        drill_fuzz_n=int(drill.get("fuzz_n", 8)),
        drill_fuzz_fpr_max=float(drill.get("fuzz_fpr_max", 0.0)),
        drill_iso_n=int(drill.get("iso_n", 8)),
        drill_iso_flip_max=float(drill.get("iso_flip_max", 0.0)),
        receipts_signer=str(receipts.get("signer", "")),
        receipts_verifier=str(receipts.get("verifier", "")),
        human_verifier=str(gate.get("human_verifier", "")),
        report_narrator=str(report.get("narrator", "")),
        report_narrator_timeout=int(report.get("narrator_timeout", 120)),
        report_suppression_patterns=suppression,
        report_sensitive_paths=tuple(str(p) for p in report.get("sensitive_paths", [])),
        contained=contained,
        source_file=path,
        sculpts=sculpts,
    )


def find_config(start: Path) -> Path | None:
    """Walk upward from `start` looking for recurve.toml — at each level the
    root file first, then the contained location (.recurve/recurve.toml)."""
    cur = start.resolve()
    for candidate in (cur, *cur.parents):
        for p in (candidate / "recurve.toml", candidate / ".recurve" / "recurve.toml"):
            if p.is_file():
                return p
    return None

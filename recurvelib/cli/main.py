"""recurve — claims-driven recursive improvement control.

Point it at a project (recurve.toml) and it turns documented claims into
probed, gated, burn-downable gaps.

    recurve ledger                 every gap across every suite (the red backlog)
    recurve show <gap-id>          one gap in full
    recurve validate               schema + invariants: every open gap has a probe
    recurve next                   value-first triage; flags review-gated gaps
    recurve run [--agent CMD]      run the burndown loop; the agent defaults to a
                                   bypass-permissions Claude (--dry-run to preview)
    recurve admit <prd>            run the admission gate on a PRD/spec — is this
                                   goal gateable at all? — print the verdict +
                                   the interview worklist (the front-door gate)
    recurve decide [--open N …]    ask the stopping controller for its stop verdict
                                   from a measured progress vector (never blind)
    recurve frontier [--point ID:W …]    surface the ranked uncovered ids — what
                                   no claim covers (the completeness frontier)
    recurve sense [--point …] [--goal …]    assemble the FULL measured progress
                                   vector — gate counts + uncovered + divergent —
                                   exactly as the loop senses it for the controller
    recurve probe [--suite S|--gap ID]   run gap probes, report RED/GREEN/BROKEN
    recurve matrix [--gate]        the conformance matrix; --gate exits nonzero on
                                   any regression, broken probe, or stale suite
    recurve status [--gate]        one-glance health: open/closed counts, the true
                                   gate verdict, broken/stale counts, pending drafts
    recurve report [--narrate]     the run report: progress, durations, ETA,
                                   diff honesty — deterministic; --narrate adds prose
    recurve freshness [--gate]     are suite artifacts current with the tree?
    recurve coverage [--gate]      does the ledger mirror every GAPS.md gap?
    recurve review <gap-id>        adversarial-review brief for review-gated gaps
    recurve drill [--fuzz|--iso|--diff]   sabotage audit: traps re-proven RED
                                   (honoring declared oracle_waiver debt); --fuzz
                                   measures per-probe fpr against generated known-bads,
                                   --iso measures verdict invariance on semantics-
                                   preserving variants, --diff alarms on disagreement
                                   with a declared reference oracle
    recurve trajectories           export the run-log as verification-gated JSONL —
                                   reward provenance per row; unverified rows excluded
    recurve import <suite>         seed a draft ledger from a suite's GAPS.md
    recurve cycle new <name> --gaps ID,ID    scaffold a sculpting-cycle plan
    recurve demo                   zero-setup sign-of-life: watch one claim go
                                   RED → GREEN behind the gate (temp dir, no config)

Exit codes: 0 ok · 1 gate/validation failure · 2 usage/parse error.
"""

from __future__ import annotations

import argparse
import sys  # noqa: F401  (kept for parity with the pre-split module)

from .base import _fail  # noqa: F401
from .commands.adjudicate import cmd_adjudicate
from .commands.admit import cmd_admit
from .commands.baseline import cmd_baseline
from .commands.coverage import cmd_coverage
from .commands.cycle_new import cmd_cycle_new
from .commands.decide import cmd_decide
from .commands.demo import cmd_demo
from .commands.drill import cmd_drill
from .commands.freshness import cmd_freshness
from .commands.frontier import cmd_frontier
from .commands.import_ import cmd_import
from .commands.init import cmd_init
from .commands.install import cmd_install
from .commands.ledger import cmd_ledger
from .commands.lock import cmd_lock
from .commands.matrix import cmd_matrix
from .commands.next import cmd_next
from .commands.pack import cmd_pack
from .commands.park import cmd_park
from .commands.probe import cmd_probe
from .commands.receipts import cmd_receipts
from .commands.record import cmd_record
from .commands.report import cmd_report
from .commands.review import cmd_review
from .commands.run import cmd_run
from .commands.sense import cmd_sense
from .commands.show import cmd_show
from .commands.stats import cmd_stats
from .commands.status import cmd_status
from .commands.trajectories import cmd_trajectories
from .commands.validate import cmd_validate

_STUBS: dict[str, str] = {}

def _stub(args):
    _fail(f"{args.prog} {args.cmd}: not yet implemented — {_STUBS[args.cmd]} (plan.md §14)")


def main(argv=None, prog: str | None = None, config_path: str | None = None):
    prog = prog or "recurve"
    p = argparse.ArgumentParser(prog=prog, description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--config", default=config_path, help="path to recurve.toml (default: search upward)")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("ledger", help="every gap across every suite").set_defaults(fn=cmd_ledger)

    s = sub.add_parser("show", help="one gap in full"); s.add_argument("gap_id"); s.set_defaults(fn=cmd_show)

    sub.add_parser("validate", help="schema + invariants").set_defaults(fn=cmd_validate)

    s = sub.add_parser("next", help="recommend the next gap (value-first; flags review-gated ones)")
    s.add_argument("--json", action="store_true", help="machine-readable triage (for orchestrators)")
    s.add_argument("--lanes", type=int, metavar="N",
                   help="deal up to N parallel lanes from pairwise-disjoint suites")
    s.set_defaults(fn=cmd_next)

    s = sub.add_parser("init", help="stamp the loop into a target (blank, --from-repo archaeology, --from-prd claimify)")
    s.add_argument("path", nargs="?",
                   help="optional target: infers the mode — a spec FILE → --from-prd, a "
                        "repo/docs DIR → --from-repo, an empty DIR → blank (always announced; "
                        "an explicit mode flag overrides)")
    s.add_argument("--target", default=".")
    s.add_argument("--name"); s.add_argument("--suite")
    s.add_argument("--tree", default=".")
    s.add_argument("--label", default="suite")
    s.add_argument("--quality", default="pre-launch", help="pre-launch | stable | <path>")
    s.add_argument("--from-repo", action="store_true", help="mine the repo's documented promises into drafts")
    s.add_argument("--from-prd", metavar="FILE", help="decompose a PRD/spec into draft claims")
    s.add_argument("--no-review", action="store_true",
                   help="skip the human draft review (NOT recommended — the skim is a security boundary)")
    s.set_defaults(fn=cmd_init)

    s = sub.add_parser("install", help="symlink the recurve entrypoint onto PATH and install the global /recurve-* skills (idempotent)")
    s.add_argument("--bin-dir", default="~/.local/bin",
                   help="directory to link recurve into (default: ~/.local/bin)")
    s.add_argument("--skills-dir", default="~/.claude/skills",
                   help="where to install the global /recurve-plan and /recurve-work skills (default: ~/.claude/skills)")
    s.add_argument("--no-skills", action="store_true",
                   help="only link the binary; skip installing the global skills")
    s.set_defaults(fn=cmd_install)

    s = sub.add_parser("run", help="run the burndown loop with sensible defaults (agent defaults to a bypass-permissions Claude)")
    s.add_argument("--agent", help="agent invocation (reads a cycle prompt on stdin); overrides $AGENT_CMD and the default")
    s.add_argument("--cap", type=int, help="max sculpting cycles (default: [burndown] cap)")
    s.add_argument("--lanes", type=int, help="run N parallel lanes (uses burndown-parallel.sh)")
    s.add_argument("--parked", help="comma-separated parked gap ids to seed this run")
    s.add_argument("--no-caffeinate", action="store_true", help="do not keep the machine awake (macOS)")
    s.add_argument("--dry-run", action="store_true", help="print the resolved agent + cap + script and exit, without running")
    s.set_defaults(fn=cmd_run)

    s = sub.add_parser("record", help="run records: append (schema-validated) / list")
    s.add_argument("action", choices=["append", "list"])
    s.add_argument("--file"); s.add_argument("--run-id")
    s.set_defaults(fn=cmd_record)

    s = sub.add_parser("review", help="print the adversarial-review brief for a review-gated gap")
    s.add_argument("gap_id")
    s.set_defaults(fn=cmd_review)

    s = sub.add_parser("probe", help="run gap probes")
    s.add_argument("--suite")
    s.add_argument("--gap"); s.add_argument("--timeout", type=int, default=120)
    s.set_defaults(fn=cmd_probe)

    s = sub.add_parser("matrix", help="the conformance matrix")
    s.add_argument("--gate", action="store_true", help="exit nonzero on regression/broken/stale/failed-trap")
    s.add_argument("--timeout", type=int, default=120)
    s.add_argument("--receipts", action="store_true", help="chain an evidence receipt per verdict")
    s.add_argument("--federate", action="append", metavar="RECURVE_TOML",
                   help="also gate another project's suites (shared-tree federation); repeatable")
    s.set_defaults(fn=cmd_matrix)

    s = sub.add_parser("decide", help="run the stopping controller on a measured progress vector and print its verdict")
    s.add_argument("--open", type=int, default=0, help="claims still RED (work remaining)")
    s.add_argument("--regressed", type=int, default=0, help="claims that went GREEN → RED this cycle")
    s.add_argument("--broken", type=int, default=0, help="claims that could not be measured")
    s.add_argument("--uncovered", type=int, default=0, help="frontier size (completeness signal)")
    s.add_argument("--divergent", action="store_true", help="a goal-counterexample passed (built the wrong thing)")
    s.set_defaults(fn=cmd_decide)

    s = sub.add_parser("admit", help="run the admission gate on a PRD/spec — is this goal gateable? — print the verdict + interview worklist")
    s.add_argument("prd", metavar="PRD", help="path to the PRD/spec file to score for gateability")
    s.add_argument("--gate", action="store_true", help="exit nonzero on a non-ADMIT verdict (refused/interview)")
    s.set_defaults(fn=cmd_admit)

    s = sub.add_parser("frontier", help="surface the ranked uncovered ids — what no claim covers")
    s.add_argument("--point", action="append", metavar="ID[:WEIGHT]",
                   help="a surface point (repeatable); WEIGHT ranks it (higher first, default 0)")
    s.add_argument("--covered", action="append", metavar="ID", help="an id a claim covers (repeatable)")
    s.add_argument("--deferred", action="append", metavar="ID", help="an id explicitly deferred (repeatable)")
    s.set_defaults(fn=cmd_frontier)

    s = sub.add_parser("sense", help="assemble the full measured progress vector — gate counts + uncovered + divergent")
    s.add_argument("--open", type=int, default=0, help="claims still RED (work remaining)")
    s.add_argument("--regressed", type=int, default=0, help="claims that went GREEN → RED this cycle")
    s.add_argument("--broken", type=int, default=0, help="claims that could not be measured")
    s.add_argument("--point", action="append", metavar="ID[:WEIGHT]",
                   help="a surface point (repeatable); WEIGHT ranks it (higher first, default 0)")
    s.add_argument("--covered", action="append", metavar="ID", help="an id a claim covers (repeatable)")
    s.add_argument("--deferred", action="append", metavar="ID", help="an id explicitly deferred (repeatable)")
    s.add_argument("--goal", action="append", metavar="ID[:WEIGHT]",
                   help="an accepted goal-counterexample (repeatable) — a divergence signal")
    s.set_defaults(fn=cmd_sense)

    s = sub.add_parser("receipts", help="evidence chains: verify / list")
    s.add_argument("action", choices=["verify", "list"])
    s.add_argument("--suite")
    s.set_defaults(fn=cmd_receipts)

    sub.add_parser("stats", help="the run-record dataset: close rates, attempts, cost by class").set_defaults(fn=cmd_stats)

    s = sub.add_parser("trajectories",
                       help="export the run-log as verification-gated JSONL — "
                            "one row per cycle record, reward provenance on every row")
    s.add_argument("--suite", help="restrict to one suite")
    s.add_argument("--include-unverified", action="store_true",
                   help="also export rows whose reward has no live probe + "
                        "non-waived trap behind it, marked verified:false")
    s.set_defaults(fn=cmd_trajectories)

    s = sub.add_parser("status", help="one-glance health: open/closed counts, the true gate verdict, broken/stale/drafts")
    s.add_argument("--gate", action="store_true", help="exit nonzero if the gate does not pass")
    s.add_argument("--timeout", type=int, default=120)
    s.set_defaults(fn=cmd_status)

    s = sub.add_parser("report", help="the run report: progress, durations, ETA, diff honesty (deterministic; --narrate adds prose)")
    s.add_argument("--suite")
    s.add_argument("--format", choices=["md", "json"], default="md")
    s.add_argument("--out", metavar="FILE", help="append the report to FILE (parents created) instead of stdout")
    s.add_argument("--narrate", action="store_true",
                   help="pipe the report + cycle records to [report] narrator and append its prose")
    s.set_defaults(fn=cmd_report)

    s = sub.add_parser("pack", help="claim packs: export a suite / install one (drafts only)")
    psub = s.add_subparsers(dest="action", required=True)
    pe = psub.add_parser("export"); pe.add_argument("suite"); pe.add_argument("--out", required=True)
    pe.add_argument("--version", default="0.1.0"); pe.set_defaults(fn=cmd_pack)
    pi = psub.add_parser("install"); pi.add_argument("path"); pi.add_argument("--suite", required=True)
    pi.set_defaults(fn=cmd_pack)

    s = sub.add_parser("freshness", help="are suite artifacts current with the target tree?")
    s.add_argument("--gate", action="store_true", help="exit nonzero if any suite is stale")
    s.set_defaults(fn=cmd_freshness)

    s = sub.add_parser("coverage", help="does the ledger mirror every GAPS.md gap? (orphans = invisible to the loop)")
    s.add_argument("--gate", action="store_true", help="exit nonzero if any prose gap has no ledger entry")
    s.set_defaults(fn=cmd_coverage)

    s = sub.add_parser("import", help="seed a draft ledger from GAPS.md")
    s.add_argument("suite"); s.add_argument("--prefix"); s.add_argument("--force", action="store_true")
    s.set_defaults(fn=cmd_import)

    c = sub.add_parser("cycle", help="sculpting cycles")
    csub = c.add_subparsers(dest="cyclecmd", required=True)
    cn = csub.add_parser("new", help="scaffold a cycle plan")
    cn.add_argument("name"); cn.add_argument("--gaps", required=True, help="comma-separated gap ids")
    cn.add_argument("--timeout", type=int, default=120)
    cn.set_defaults(fn=cmd_cycle_new)

    s = sub.add_parser("baseline", help="the promotion ceremony: drafts → measured ledger entries")
    s.add_argument("suite"); s.add_argument("--timeout", type=int, default=120)
    s.set_defaults(fn=cmd_baseline)

    sub.add_parser("demo", help="zero-setup sign-of-life: watch one claim go RED → GREEN behind the gate (temp dir, no config)").set_defaults(fn=cmd_demo)

    s = sub.add_parser("park", help="park a gap (run state, not claim truth) / list parked")
    s.add_argument("gap_id", nargs="?")
    s.add_argument("--reason"); s.add_argument("--attempt"); s.add_argument("--observed")
    s.add_argument("--unpark", action="store_true")
    s.set_defaults(fn=cmd_park)

    s = sub.add_parser("lock", help="tree lock: status / acquire / release (orchestrators) / steal (human-confirmed only)")
    s.add_argument("action", choices=["status", "acquire", "release", "steal"])
    s.set_defaults(fn=cmd_lock)

    s = sub.add_parser("adjudicate", help="record a human decision in three synchronized places / amend / retire")
    s.add_argument("gap_id")
    s.add_argument("--decision", help="the one human sentence (omit for interactive prompt)")
    s.add_argument("--retire", action="store_true",
                   help="retire the claim: prose tombstone + probe deleted + entry removed, one change")
    s.set_defaults(fn=cmd_adjudicate)

    s = sub.add_parser("drill", help="sabotage audit: re-prove the guards can still fail (scratch-only, traceless)")
    s.add_argument("--suite"); s.add_argument("--timeout", type=int, default=120)
    s.add_argument("--deep", action="store_true", help="also run per-suite harness/drill.sh hooks on a scratch tree copy")
    s.add_argument("--fuzz", action="store_true",
                   help="also run probes/<id>.fuzz.sh generators and measure each "
                        "probe's false-positive rate against generated known-bads "
                        "([drill] fuzz_n / fuzz_fpr_max bound cost and threshold)")
    s.add_argument("--iso", action="store_true",
                   help="also run probes/<id>.iso.sh generators and measure each "
                        "probe's verdict invariance on semantics-preserving variants "
                        "([drill] iso_n / iso_flip_max bound cost and threshold)")
    s.add_argument("--diff", action="store_true",
                   help="also run each claim's declared reference oracle "
                        "(probes/<id>.ref.sh) and alarm on disagreement with the probe")
    s.set_defaults(fn=cmd_drill)

    for name in _STUBS:
        s = sub.add_parser(name, help=_STUBS[name])
        s.add_argument("rest", nargs="*")
        s.set_defaults(fn=_stub)

    args = p.parse_args(argv)
    args.prog = prog
    args.fn(args)


if __name__ == "__main__":
    main()

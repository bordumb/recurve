"""recurve — claims-driven recursive improvement control.

Point it at a project (recurve.toml) and it turns documented claims into
probed, gated, burn-downable gaps. This module is the Typer dispatch layer:
every command's argument surface is declared here and forwarded to the
unchanged `cmd_*` body in `.commands.<name>`. The engine's behavior lives in
those bodies; this file only parses and routes.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import List, Optional

import typer

from .base import (  # noqa: F401  (_fail re-exported for parity)
    LockAction,
    ReceiptsAction,
    RecordAction,
    ReportFormat,
    _fail,
)
from .commands.adjudicate import cmd_adjudicate
from .commands.admit import cmd_admit
from .commands.baseline import cmd_baseline
from .commands.coverage import cmd_coverage
from .commands.cycle_new import cmd_cycle_new
from .commands.decide import cmd_decide
from .commands.demo import cmd_demo
from .commands.drill import cmd_drill
from .commands.fansearch import fansearch_app
from .commands.freshness import cmd_freshness
from .commands.frontier import cmd_frontier
from .commands.governor import cmd_governor
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

# The global --config value and program name are stashed by the root callback
# (Typer evaluates option defaults at import time, so the config_path passed to
# main() must reach commands through here, not through a decorator default).
_PROG = "recurve"
_CONFIG: Optional[str] = None
_CONFIG_DEFAULT: Optional[str] = None


def _ns(cmd: str, **kw) -> SimpleNamespace:
    """Build the args namespace every cmd_* body reads, carrying the global
    --config and prog alongside the command's own parsed parameters."""
    return SimpleNamespace(cmd=cmd, prog=_PROG, config=_CONFIG, **kw)


app = typer.Typer(
    add_completion=False,
    no_args_is_help=True,
    rich_markup_mode=None,          # plain click help — no rich color/chrome (R3.3)
    pretty_exceptions_enable=False,  # never reformat/colour a traceback
    help="recurve — claims-driven recursive improvement control.",
)


@app.callback()
def _root(
    config: Optional[str] = typer.Option(
        None, "--config", help="path to recurve.toml (default: search upward)"),
):
    global _CONFIG
    _CONFIG = config if config is not None else _CONFIG_DEFAULT


@app.command(help="every gap across every suite")
def ledger():
    cmd_ledger(_ns("ledger"))


@app.command(help="one gap in full")
def show(gap_id: str = typer.Argument(...)):
    cmd_show(_ns("show", gap_id=gap_id))


@app.command(help="schema + invariants")
def validate():
    cmd_validate(_ns("validate"))


@app.command(help="recommend the next gap (value-first; flags review-gated ones)")
def next(
    json: bool = typer.Option(False, "--json", help="machine-readable triage (for orchestrators)"),
    lanes: Optional[int] = typer.Option(None, "--lanes", help="deal up to N parallel lanes from pairwise-disjoint suites"),
):
    cmd_next(_ns("next", json=json, lanes=lanes))


@app.command(help="stamp the loop into a target (blank, --from-repo archaeology, --from-prd claimify)")
def init(
    path: Optional[str] = typer.Argument(None, help="optional target: a spec FILE → --from-prd, a repo/docs DIR → --from-repo, an empty DIR → blank"),
    target: str = typer.Option(".", "--target"),
    name: Optional[str] = typer.Option(None, "--name"),
    suite: Optional[str] = typer.Option(None, "--suite"),
    tree: str = typer.Option(".", "--tree"),
    label: str = typer.Option("suite", "--label"),
    quality: str = typer.Option("pre-launch", "--quality", help="pre-launch | stable | <path>"),
    from_repo: bool = typer.Option(False, "--from-repo", help="mine the repo's documented promises into drafts"),
    from_prd: Optional[str] = typer.Option(None, "--from-prd", metavar="FILE", help="decompose a PRD/spec into draft claims"),
    no_review: bool = typer.Option(False, "--no-review", help="skip the human draft review (NOT recommended)"),
):
    cmd_init(_ns("init", path=path, target=target, name=name, suite=suite, tree=tree,
                 label=label, quality=quality, from_repo=from_repo, from_prd=from_prd,
                 no_review=no_review))


@app.command(help="symlink the recurve entrypoint onto PATH and install the global /recurve-* skills (idempotent)")
def install(
    bin_dir: str = typer.Option("~/.local/bin", "--bin-dir", help="directory to link recurve into"),
    skills_dir: str = typer.Option("~/.claude/skills", "--skills-dir", help="where to install the global skills"),
    no_skills: bool = typer.Option(False, "--no-skills", help="only link the binary; skip the global skills"),
):
    cmd_install(_ns("install", bin_dir=bin_dir, skills_dir=skills_dir, no_skills=no_skills))


@app.command(help="run the burndown loop with sensible defaults")
def run(
    agent: Optional[str] = typer.Option(None, "--agent", help="agent invocation (reads a cycle prompt on stdin)"),
    cap: Optional[int] = typer.Option(None, "--cap", help="max sculpting cycles"),
    lanes: Optional[int] = typer.Option(None, "--lanes", help="run N parallel lanes"),
    parked: Optional[str] = typer.Option(None, "--parked", help="comma-separated parked gap ids to seed"),
    no_caffeinate: bool = typer.Option(False, "--no-caffeinate", help="do not keep the machine awake (macOS)"),
    dry_run: bool = typer.Option(False, "--dry-run", help="print the resolved agent + cap + script and exit"),
):
    cmd_run(_ns("run", agent=agent, cap=cap, lanes=lanes, parked=parked,
                no_caffeinate=no_caffeinate, dry_run=dry_run))


@app.command(help="run records: append (schema-validated) / list")
def record(
    action: RecordAction = typer.Argument(...),
    file: Optional[str] = typer.Option(None, "--file"),
    run_id: Optional[str] = typer.Option(None, "--run-id"),
):
    cmd_record(_ns("record", action=action.value, file=file, run_id=run_id))


@app.command(help="print the adversarial-review brief for a review-gated gap")
def review(gap_id: str = typer.Argument(...)):
    cmd_review(_ns("review", gap_id=gap_id))


@app.command(help="run gap probes")
def probe(
    suite: Optional[str] = typer.Option(None, "--suite"),
    gap: Optional[str] = typer.Option(None, "--gap"),
    timeout: int = typer.Option(120, "--timeout"),
):
    cmd_probe(_ns("probe", suite=suite, gap=gap, timeout=timeout))


@app.command(help="the conformance matrix")
def matrix(
    gate: bool = typer.Option(False, "--gate", help="exit nonzero on regression/broken/stale/failed-trap"),
    timeout: int = typer.Option(120, "--timeout"),
    receipts: bool = typer.Option(False, "--receipts", help="chain an evidence receipt per verdict"),
    cache: bool = typer.Option(False, "--cache", help="skip probes whose check-file + imported oleans are unchanged since the last GREEN/RED (sound; run the full uncached gate before merge/report/baseline)"),
    federate: Optional[List[str]] = typer.Option(None, "--federate", metavar="RECURVE_TOML", help="also gate another project's suites; repeatable"),
):
    cmd_matrix(_ns("matrix", gate=gate, timeout=timeout, receipts=receipts, cache=cache, federate=federate))


@app.command(help="run the stopping controller on a measured progress vector")
def decide(
    open: int = typer.Option(0, "--open", help="claims still RED"),
    regressed: int = typer.Option(0, "--regressed", help="claims that went GREEN → RED this cycle"),
    broken: int = typer.Option(0, "--broken", help="claims that could not be measured"),
    uncovered: int = typer.Option(0, "--uncovered", help="frontier size"),
    divergent: bool = typer.Option(False, "--divergent", help="a goal-counterexample passed"),
):
    cmd_decide(_ns("decide", open=open, regressed=regressed, broken=broken,
                   uncovered=uncovered, divergent=divergent))


@app.command(help="run the admission gate on a PRD/spec")
def admit(
    prd: str = typer.Argument(..., metavar="PRD", help="path to the PRD/spec file to score"),
    gate: bool = typer.Option(False, "--gate", help="exit nonzero on a non-ADMIT verdict"),
):
    cmd_admit(_ns("admit", prd=prd, gate=gate))


@app.command(help="surface the ranked uncovered ids — what no claim covers")
def frontier(
    point: Optional[List[str]] = typer.Option(None, "--point", metavar="ID[:WEIGHT]", help="a surface point (repeatable)"),
    covered: Optional[List[str]] = typer.Option(None, "--covered", metavar="ID", help="an id a claim covers (repeatable)"),
    deferred: Optional[List[str]] = typer.Option(None, "--deferred", metavar="ID", help="an id explicitly deferred (repeatable)"),
):
    cmd_frontier(_ns("frontier", point=point, covered=covered, deferred=deferred))


@app.command(help="assemble the full measured progress vector")
def sense(
    open: int = typer.Option(0, "--open"),
    regressed: int = typer.Option(0, "--regressed"),
    broken: int = typer.Option(0, "--broken"),
    point: Optional[List[str]] = typer.Option(None, "--point", metavar="ID[:WEIGHT]"),
    covered: Optional[List[str]] = typer.Option(None, "--covered", metavar="ID"),
    deferred: Optional[List[str]] = typer.Option(None, "--deferred", metavar="ID"),
    goal: Optional[List[str]] = typer.Option(None, "--goal", metavar="ID[:WEIGHT]"),
):
    cmd_sense(_ns("sense", open=open, regressed=regressed, broken=broken,
                  point=point, covered=covered, deferred=deferred, goal=goal))


@app.command(help="evidence chains: verify / list")
def receipts(
    action: ReceiptsAction = typer.Argument(...),
    suite: Optional[str] = typer.Option(None, "--suite"),
):
    cmd_receipts(_ns("receipts", action=action.value, suite=suite))


@app.command(help="the run-record dataset: close rates, attempts, cost by class")
def stats():
    cmd_stats(_ns("stats"))


@app.command(help="export the run-log as verification-gated JSONL")
def trajectories(
    suite: Optional[str] = typer.Option(None, "--suite", help="restrict to one suite"),
    include_unverified: bool = typer.Option(False, "--include-unverified", help="also export rows with no live probe+trap, marked verified:false"),
):
    cmd_trajectories(_ns("trajectories", suite=suite, include_unverified=include_unverified))


@app.command(help="one-glance health: open/closed counts, the true gate verdict, broken/stale/drafts")
def status(
    gate: bool = typer.Option(False, "--gate", help="exit nonzero if the gate does not pass"),
    timeout: int = typer.Option(120, "--timeout"),
):
    cmd_status(_ns("status", gate=gate, timeout=timeout))


@app.command(help="the run report: progress, durations, ETA, diff honesty")
def report(
    suite: Optional[str] = typer.Option(None, "--suite"),
    format: ReportFormat = typer.Option(ReportFormat.md, "--format"),
    out: Optional[str] = typer.Option(None, "--out", metavar="FILE", help="append the report to FILE instead of stdout"),
    narrate: bool = typer.Option(False, "--narrate", help="pipe the report + records to [report] narrator and append its prose"),
):
    cmd_report(_ns("report", suite=suite, format=format.value, out=out, narrate=narrate))


pack_app = typer.Typer(rich_markup_mode=None, help="claim packs: export a suite / install one (drafts only)")


@pack_app.command("export")
def _pack_export(
    suite: str = typer.Argument(...),
    out: str = typer.Option(..., "--out"),
    version: str = typer.Option("0.1.0", "--version"),
):
    cmd_pack(_ns("pack", action="export", suite=suite, out=out, version=version))


@pack_app.command("install")
def _pack_install(
    path: str = typer.Argument(...),
    suite: str = typer.Option(..., "--suite"),
):
    cmd_pack(_ns("pack", action="install", path=path, suite=suite))

app.add_typer(pack_app, name="pack")


@app.command(help="are suite artifacts current with the target tree?")
def freshness(
    gate: bool = typer.Option(False, "--gate", help="exit nonzero if any suite is stale"),
):
    cmd_freshness(_ns("freshness", gate=gate))


@app.command(help="does the ledger mirror every GAPS.md gap?")
def coverage(
    gate: bool = typer.Option(False, "--gate", help="exit nonzero if any prose gap has no ledger entry"),
):
    cmd_coverage(_ns("coverage", gate=gate))


@app.command(name="import", help="seed a draft ledger from GAPS.md")
def import_(
    suite: str = typer.Argument(...),
    prefix: Optional[str] = typer.Option(None, "--prefix"),
    force: bool = typer.Option(False, "--force"),
):
    cmd_import(_ns("import", suite=suite, prefix=prefix, force=force))


cycle_app = typer.Typer(rich_markup_mode=None, help="sculpting cycles")


@cycle_app.command("new")
def _cycle_new(
    name: str = typer.Argument(...),
    gaps: str = typer.Option(..., "--gaps", help="comma-separated gap ids"),
    timeout: int = typer.Option(120, "--timeout"),
):
    cmd_cycle_new(_ns("cycle", cyclecmd="new", name=name, gaps=gaps, timeout=timeout))

app.add_typer(cycle_app, name="cycle")
app.add_typer(fansearch_app, name="fansearch")


@app.command(help="the promotion ceremony: drafts → measured ledger entries")
def baseline(
    suite: str = typer.Argument(...),
    timeout: int = typer.Option(120, "--timeout"),
):
    cmd_baseline(_ns("baseline", suite=suite, timeout=timeout))


@app.command(help="zero-setup sign-of-life: watch one claim go RED → GREEN behind the gate")
def demo():
    cmd_demo(_ns("demo"))


@app.command(help="park a gap (run state, not claim truth) / list parked")
def park(
    gap_id: Optional[str] = typer.Argument(None),
    reason: Optional[str] = typer.Option(None, "--reason"),
    attempt: Optional[str] = typer.Option(None, "--attempt"),
    observed: Optional[str] = typer.Option(None, "--observed"),
    unpark: bool = typer.Option(False, "--unpark"),
):
    cmd_park(_ns("park", gap_id=gap_id, reason=reason, attempt=attempt,
                 observed=observed, unpark=unpark))


@app.command(help="human_required governor: verify + register a signed attestation")
def governor(
    action: str = typer.Argument(..., help="approve"),
    claim_ids: List[str] = typer.Argument(None, help="claim id(s) the attestation covers"),
    attestation: str = typer.Option(..., "--attestation", help="path to the signed attestation JSON"),
    ref: Optional[str] = typer.Option(None, "--ref", help="commit the attestation's hash binds to, "
                                      "if not already recorded in the attestation payload"),
):
    cmd_governor(_ns("governor", action=action, claim_ids=claim_ids or [],
                     attestation=attestation, ref=ref))


@app.command(help="tree lock: status / acquire / release / steal")
def lock(action: LockAction = typer.Argument(...)):
    cmd_lock(_ns("lock", action=action.value))


@app.command(help="record a human decision in three synchronized places / amend / retire")
def adjudicate(
    gap_id: str = typer.Argument(...),
    decision: Optional[str] = typer.Option(None, "--decision", help="the one human sentence"),
    retire: bool = typer.Option(False, "--retire", help="retire the claim: tombstone + probe deleted + entry removed"),
):
    cmd_adjudicate(_ns("adjudicate", gap_id=gap_id, decision=decision, retire=retire))


@app.command(help="sabotage audit: re-prove the guards can still fail (scratch-only, traceless)")
def drill(
    suite: Optional[str] = typer.Option(None, "--suite"),
    timeout: int = typer.Option(120, "--timeout"),
    deep: bool = typer.Option(False, "--deep", help="also run per-suite harness/drill.sh hooks on a scratch tree copy"),
    fuzz: bool = typer.Option(False, "--fuzz", help="also run probes/<id>.fuzz.sh generators and measure per-probe fpr"),
    iso: bool = typer.Option(False, "--iso", help="also run probes/<id>.iso.sh generators and measure verdict invariance"),
    diff: bool = typer.Option(False, "--diff", help="also run each claim's declared reference oracle and alarm on disagreement"),
    fansearch: bool = typer.Option(False, "--fansearch", help="also measure each registered ProxyEvaluator's known-good/known-bad separation"),
):
    cmd_drill(_ns("drill", suite=suite, timeout=timeout, deep=deep, fuzz=fuzz, iso=iso, diff=diff, fansearch=fansearch))

def main(argv=None, prog: str | None = None, config_path: str | None = None):
    global _PROG, _CONFIG, _CONFIG_DEFAULT
    _PROG = prog or "recurve"
    _CONFIG_DEFAULT = config_path
    _CONFIG = config_path
    app(args=argv, prog_name=_PROG)


if __name__ == "__main__":
    main()

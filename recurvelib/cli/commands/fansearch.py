from __future__ import annotations

from typing import Optional

import typer

from ..base import *  # shared recurvelib imports
from ..base import _fail, _config


def _args(**kw):
    """Build the args namespace these cmd_* bodies read. Deferred import:
    `..main` imports this module's `fansearch_app` at load time, so this
    module cannot import `..main` at its own top level."""
    from ..main import _ns
    return _ns("fansearch", **kw)


fansearch_app = typer.Typer(rich_markup_mode=None,
                            help="discovery search over a registered proxy domain")


@fansearch_app.command("run")
def _fansearch_run(
    domain: str = typer.Argument(...),
    ns_repo: Optional[str] = typer.Option(None, "--ns-repo", help="path to the target repo a compiled candidate is checked against"),
    budget: float = typer.Option(60.0, "--budget", help="wall-clock seconds"),
    dry_generations: int = typer.Option(3, "--dry-generations"),
    seed: int = typer.Option(0, "--seed"),
):
    cmd_fansearch_run(_args(domain=domain, ns_repo=ns_repo, budget=budget,
                           dry_generations=dry_generations, seed=seed))


@fansearch_app.command("status")
def _fansearch_status(domain: Optional[str] = typer.Option(None, "--domain")):
    cmd_fansearch_status(_args(domain=domain))


@fansearch_app.command("archive")
def _fansearch_archive(domain: str = typer.Argument(...)):
    cmd_fansearch_archive(_args(domain=domain))


@fansearch_app.command("promote")
def _fansearch_promote(
    domain: str = typer.Argument(...),
    round: int = typer.Argument(...),
    claim_id: str = typer.Option(..., "--claim-id"),
    ns_repo: Optional[str] = typer.Option(None, "--ns-repo"),
):
    cmd_fansearch_promote(_args(domain=domain, round=round, claim_id=claim_id, ns_repo=ns_repo))


@fansearch_app.command("drill")
def _fansearch_drill():
    cmd_fansearch_drill(_args())


def cmd_fansearch_run(args):
    from recurvelib.fansearch.campaign import CampaignError, run_campaign

    cfg = _config(args)
    try:
        summary = run_campaign(
            cfg, args.domain, args.ns_repo,
            budget_seconds=args.budget, dry_generations=args.dry_generations,
            seed0=args.seed,
        )
    except CampaignError as e:
        _fail(f"\033[31m✗ {e}\033[0m", 1)
        return
    print(f"domain {summary.domain}: {summary.rounds} round(s) this run, "
          f"{summary.records} new record(s), {summary.gate_confirmed} gate-confirmed, "
          f"stopped: {summary.stopped_reason}")
    if not args.ns_repo:
        print("(no --ns-repo given: candidates were scored but never checked against a real "
              "gate, so nothing could be gate-confirmed)")


def cmd_fansearch_status(args):
    from recurvelib.fansearch.campaign import archive_path, read_archive
    from recurvelib.adapters.proxy import PROXY_ADAPTERS

    cfg = _config(args)
    domains = [args.domain] if args.domain else sorted(k for k in PROXY_ADAPTERS if k != "off")
    for domain in domains:
        entries = read_archive(archive_path(cfg, domain))
        if not entries:
            print(f"{domain}: no candidates tried yet")
            continue
        best = max(entries, key=lambda e: e["proxy_score"])
        confirmed = [e for e in entries if e["gate_status"] == "gate_confirmed"]
        print(f"{domain}: {len(entries)} candidate(s) tried, best score {best['proxy_score']:.3f} "
              f"(round {best['round']}), {len(confirmed)} gate-confirmed")


def cmd_fansearch_archive(args):
    from recurvelib.fansearch.campaign import archive_path, read_archive

    cfg = _config(args)
    entries = read_archive(archive_path(cfg, args.domain))
    if not entries:
        print(f"{args.domain}: no candidates tried yet")
        return
    for e in entries:
        marker = "*" if e["is_record"] else " "
        print(f"{marker} round {e['round']:<4} N={e['N']:<3} score={e['proxy_score']:.3f} "
              f"status={e['gate_status']}")


def cmd_fansearch_promote(args):
    from recurvelib.fansearch.promote import PromoteError, promote_candidate

    cfg = _config(args)
    if not args.ns_repo:
        _fail("--ns-repo is required to promote a candidate into a target repo", 1)
        return
    try:
        result = promote_candidate(cfg, args.domain, args.ns_repo, args.round, args.claim_id)
    except PromoteError as e:
        _fail(f"\033[31m✗ {e}\033[0m", 1)
        return
    if not result.ok:
        _fail(f"\033[31m✗ {result.claim_id} not promoted:\033[0m {result.detail}", 1)
        return
    print(f"✓ {result.claim_id} promoted and closed: {result.detail}")


def cmd_fansearch_drill(args):
    from recurvelib.cli.commands.drill import cmd_drill
    from types import SimpleNamespace
    cmd_drill(SimpleNamespace(cmd="drill", config=getattr(args, "config", None),
                             suite=None, timeout=120, deep=False, fuzz=False, iso=False,
                             diff=False, fansearch=True))

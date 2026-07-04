from __future__ import annotations

from ..base import *  # shared recurvelib imports
from ..base import (
    _fail,
    _config,
    _load,
    _filter,
    _parse_point,
    _parse_goal,
    _draft_backlog,
)

def cmd_review(args):
    """Print the adversarial-review brief for a review-gated gap — the brief you
    hand to an INDEPENDENT reviewer (an agent/human prompted to REFUTE the
    change's safety), not to the implementer."""
    from recurvelib.io import render
    C = render.C
    cfg = _config(args)
    prog = args.prog
    g = _load(cfg).by_id(args.gap_id)
    if not g:
        print(f"unknown gap id: {args.gap_id}", file=sys.stderr)
        raise SystemExit(2)
    if not review_gated(g):
        print(f"{C['green']}{g.id} is not review-gated (class={g.gap_class.value}).{C['reset']} "
              f"It fails loud — a green `{prog} matrix --gate` is sufficient to promote it.")
        return
    print(f"{C['bold']}ADVERSARIAL REVIEW BRIEF — {g.id}{C['reset']}  ({g.gap_class.value})")
    print(f"  {g.title}\n")
    print(f"  change under review: {g.smallest_fix}")
    print(f"  was observed today:  {g.observed or '—'}\n")
    print(f"{C['amber']}  The reviewer's job is to BREAK it, not confirm it.{C['reset']} A green gate")
    print( "  proves the INTENDED case works; it does not prove the change is safe.")
    print( "  Find an input the loosened check now WRONGLY accepts. Specifically:")
    print( "    1. Enumerate what the new check accepts that the old one rejected.")
    print( "       For each, ask: is that acceptance always legitimate?")
    print( "    2. The suite's own adversarial probes are a FLOOR, not a ceiling —")
    print( "       invent NEW attacks (replay, reorder, forge, substitute identity).")
    print( "    3. If the fix relies on a corroboration source (witness / log / receipt),")
    print( "       attack THAT source's trust assumption, not just the happy path.")
    print( "    4. Re-read the upstream comment that made this fail-closed — it named")
    print( "       the threat. Confirm the loosening doesn't re-open exactly that.\n")
    print(f"{C['amber']}  Promote open→closed ONLY IF all hold:{C['reset']}")
    print( "    · the reviewer could not break it, and said so explicitly;")
    print( "    · the reviewer is INDEPENDENT of the implementer (different agent/pass);")
    print(f"    · `{prog} matrix --gate` is green fleet-wide;")
    print( "    · a new RED probe was added for any attack the reviewer tried (so the")
    print( "      next cycle guards it). Otherwise: leave open, record the finding.")

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

def cmd_admit(args):
    """Run the admission gate on a PRD/spec — is this goal gateable at all? —
    and print the verdict plus the interview worklist. A thin honest report over
    `claimify.admit_result`, which maps the parsed drafts to admission
    assertions and runs `admission.admit`. This is the same gate `init
    --from-prd` runs at the front; running it standalone lets a human (or an
    orchestrator) score a goal before committing to claimify it."""
    from ...admission import Verdict
    from ...claimify import admit_result, parse_prd
    prd = Path(args.prd)
    if not prd.exists():
        _fail(f"no such PRD/spec file: {prd}")
    res = parse_prd(prd.read_text(errors="replace"), prd.name)
    report = admit_result(res)
    by_num = {str(c.num): c for c in res.claims}
    print(f"verdict     {report.verdict.value}")
    print(f"gateability {report.gateability:.2f}  ({report.probeable}/{report.total} probe-able)")
    if report.worklist:
        print("worklist (interview these toward checks):")
        seen: set = set()
        for aid, gaps in report.worklist:
            if aid in seen:
                continue
            seen.add(aid)
            draft = by_num.get(aid)
            quote = (draft.sentence if draft else aid)[:100]
            print(f"  - \"{quote}\": {'; '.join(gaps)}")
    if args.gate and report.verdict is not Verdict.ADMIT:
        raise SystemExit(1)

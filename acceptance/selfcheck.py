#!/usr/bin/env python3
"""Engine self-checks the migration diff can't see: the probe exit-code
contract's totality, and the run-record/receipt validators."""

import subprocess
import sys
import tempfile
from pathlib import Path

RECURVE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RECURVE))

from recurvelib.records import (  # noqa: E402
    RECORD_SCHEMA_VERSION, RecordError, make_receipt, receipt_hash,
    validate_receipt, validate_run_record,
)


def check_probe_totality():
    """Exit 0→GREEN, 1→RED, anything else (incl. crash/127) → BROKEN."""
    from recurvelib.model import Gap, GapClass, Severity, Status
    from recurvelib.probe import Outcome, ShellProbeRunner

    cases = [("exit 0", Outcome.GREEN), ("exit 1", Outcome.RED),
             ("exit 2", Outcome.BROKEN), ("exit 7", Outcome.BROKEN),
             ("kill -SEGV $$", Outcome.BROKEN), ("no_such_command_xyz", Outcome.BROKEN)]
    with tempfile.TemporaryDirectory() as td:
        suite_dir = Path(td)
        probes = suite_dir / "probes"
        probes.mkdir()
        for i, (body, want) in enumerate(cases):
            probe = probes / f"p{i}.sh"
            probe.write_text(f"#!/usr/bin/env bash\n{body}\n")
            gap = Gap(id=f"T-{i}", suite="t", title="t", gap_class=GapClass.FRICTION,
                      status=Status.OPEN, severity=Severity.COSMETIC, evidence=(),
                      observed="", smallest_fix="t", unlocks="", reads="none",
                      covers=(), probe=probe, source_file=suite_dir / "gaps.yaml")
            got = ShellProbeRunner().run(gap, timeout_s=10).outcome
            assert got is want, f"probe {body!r}: got {got}, want {want}"
    print("probe exit-code map is total")


def check_records():
    r1 = make_receipt(gap="X-1", suite="s", verdict="RED", exit_code=1, detail="d",
                      probe_path=None, tree_kind="git", tree_value="abc",
                      oracle_versions={"peer": "1.0"},
                      observed_at="2026-01-01T00:00:00Z", prev=None)
    validate_receipt(r1)
    r2 = make_receipt(gap="X-1", suite="s", verdict="GREEN", exit_code=0, detail="",
                      probe_path=None, tree_kind="git", tree_value="def",
                      oracle_versions={}, observed_at="2026-01-01T01:00:00Z",
                      prev=r1["self_sha256"])
    validate_receipt(r2)
    assert r2["prev"] == receipt_hash(r1)
    tampered = dict(r2, verdict="RED")
    try:
        validate_receipt(tampered)
        raise AssertionError("tampered receipt validated")
    except RecordError:
        pass

    rec = {"schema_version": RECORD_SCHEMA_VERSION, "project": "p", "cycle": "c",
           "status": "closed", "attempts": 1, "wall_clock_s": 1.0,
           "verdicts_before": {"green": 0, "red": 1},
           "verdicts_after": {"green": 1, "red": 0}}
    validate_run_record(rec)
    for bad in [dict(rec, status="maybe"), dict(rec, extra=1),
                {k: v for k, v in rec.items() if k != "attempts"}]:
        try:
            validate_run_record(bad)
            raise AssertionError(f"bad record validated: {bad}")
        except RecordError:
            pass
    print("records: chain, tamper detection, validation")


if __name__ == "__main__":
    check_probe_totality()
    check_records()
    print("selfcheck OK")

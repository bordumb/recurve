#!/usr/bin/env bash
# TK-6: a receipt edited after the fact fails validation loudly.
ROOT="$(cd "$(dirname "$0")/../../../.." && pwd)"
python3 - "$ROOT" "${TRAP_FIXTURE:-}" <<'PYEOF'
import importlib.util
import sys
from pathlib import Path

root, fixture = sys.argv[1], sys.argv[2]
sys.path.insert(0, root)
from recurvelib.io.records import make_receipt

if fixture:
    spec = importlib.util.spec_from_file_location(
        "rstub", Path(fixture) / "trusting_validator.py")
    stub = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(stub)
    validate, RecordError = stub.validate_receipt, stub.RecordError
else:
    from recurvelib.io.records import RecordError
    from recurvelib.io.records import validate_receipt as validate

r = make_receipt(gap="T-1", suite="s", verdict="GREEN", exit_code=0, detail="",
                 probe_path=None, tree_kind="git", tree_value="abc",
                 oracle_versions={}, observed_at="2026-01-01T00:00:00Z", prev=None)
tampered = dict(r, verdict="RED")
try:
    validate(tampered)
    print("ours=tampered receipt accepted oracle=self-hash mismatch raises")
    sys.exit(1)
except RecordError:
    print("tampered receipt rejected — the evidence is tamper-evident")
    sys.exit(0)
PYEOF

#!/bin/bash
# FS-7: a claim's receipt carries which domain proposed it and what the
# untrusted proxy scored it at promotion time, only when a campaign
# actually promoted it -- hand-authored claims get no such field.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$HERE/../../../.." && pwd)"

if [ -n "${TRAP_FIXTURE:-}" ]; then
  IMPL="$TRAP_FIXTURE/receipts.py"
else
  IMPL="$ROOT/recurvelib/io/receipts.py"
fi

python3 - "$ROOT" "$IMPL" <<'PYEOF'
import importlib.util
import json
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

root, impl_path = sys.argv[1], sys.argv[2]
sys.path.insert(0, root)

spec = importlib.util.spec_from_file_location("receipts_candidate", impl_path)
mod = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = mod
try:
    spec.loader.exec_module(mod)
except Exception as e:
    print(f"RED: receipts module failed to import: {e}")
    sys.exit(1)

from recurvelib.io.records import validate_receipt

with tempfile.TemporaryDirectory() as tmp:
    state_dir = Path(tmp)
    (state_dir / "fansearch").mkdir()
    (state_dir / "fansearch" / "promotions.jsonl").write_text(
        json.dumps({"gap": "X-1", "domain": "dyadic_lyapunov", "proxy_score": 0.91,
                    "round": 3}) + "\n"
    )
    def suite_for(_name):
        return SimpleNamespace(dir=state_dir)  # no harness/versions.lock here -> {} versions

    config = SimpleNamespace(state_dir=state_dir, tree=None, receipts_signer="",
                             suite_for=suite_for)

    def gap(id_, suite="fansearch"):
        return SimpleNamespace(id=id_, suite=suite, probe=None)

    def result(gap_id):
        return SimpleNamespace(gap=gap(gap_id), outcome=SimpleNamespace(value="GREEN"),
                               exit_code=0, detail="ok")

    matrix = SimpleNamespace(results=[result("X-1"), result("X-2")])
    n = mod.emit_for_matrix(config, matrix)
    if n != 2:
        print(f"RED: expected 2 receipts emitted, got {n}")
        sys.exit(1)

    receipts = mod.ReceiptChain(config, "fansearch").receipts()
    by_gap = {r["gap"]: r for r in receipts}

    if "discovery" not in by_gap.get("X-1", {}):
        print("RED: X-1 (promoted by a campaign) has no discovery field on its receipt")
        sys.exit(1)
    if by_gap["X-1"]["discovery"] != {"domain": "dyadic_lyapunov", "proxy_score": 0.91}:
        print(f"RED: X-1's discovery field is wrong: {by_gap['X-1']['discovery']}")
        sys.exit(1)
    if "discovery" in by_gap.get("X-2", {}):
        print("RED: X-2 (not in promotions.jsonl) should carry no discovery field")
        sys.exit(1)

    for r in receipts:
        validate_receipt(r)

print("GREEN: only the promoted gap's receipt carries discovery provenance; both validate")
sys.exit(0)
PYEOF

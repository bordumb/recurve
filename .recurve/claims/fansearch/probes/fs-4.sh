#!/bin/bash
# FS-4: compile_to_claim's output actually elaborates through the real
# gate in the sibling navier_stokes repo -- the promotion bridge itself,
# automated (F5), not hand-authored (F0 Stage 3 / SH7).
set -u

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$HERE/../../../.." && pwd)"

if [ -n "${TRAP_FIXTURE:-}" ]; then
  COMPILE_SRC="$TRAP_FIXTURE/compile_to_claim.py"
else
  COMPILE_SRC="$ROOT/recurvelib/adapters/proxy/compile_to_claim.py"
fi

# $NAVIER_STOKES_REPO overrides (e.g. a checkout/worktree ahead of whatever
# is on the default branch); otherwise walk up from ROOT (a worktree can sit
# several levels under the real repo) to find the auths-base directory
# holding both recurve/ and navier_stokes/ as siblings.
if [ -n "${NAVIER_STOKES_REPO:-}" ]; then
  NS_REPO="$NAVIER_STOKES_REPO"
else
  d="$ROOT"
  NS_REPO=""
  while [ "$d" != "/" ]; do
    if [ -f "$d/navier_stokes/NavierStokes/Shells/Basic.lean" ]; then
      NS_REPO="$d/navier_stokes"
      break
    fi
    d="$(dirname "$d")"
  done
fi

if [ -z "$NS_REPO" ] || [ ! -d "$NS_REPO" ]; then
  echo "sibling navier_stokes repo not found — cannot verify the promotion bridge for real"
  exit 2
fi

command -v lake >/dev/null 2>&1 || { echo "lake not on PATH"; exit 3; }
grep -q "^theorem shell_single_active_dissipative" "$NS_REPO/NavierStokes/Shells/Basic.lean" 2>/dev/null \
  || { echo "shell_single_active_dissipative (SH7) not found in the sibling repo — external oracle absent"; exit 3; }

python3 - "$ROOT" "$COMPILE_SRC" "$NS_REPO" <<'PYEOF'
import importlib.util
import subprocess
import sys
import tempfile
from pathlib import Path

root, compile_src, ns_repo = sys.argv[1], sys.argv[2], sys.argv[3]
sys.path.insert(0, root)

spec = importlib.util.spec_from_file_location("compile_to_claim_candidate", compile_src)
mod = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = mod
try:
    spec.loader.exec_module(mod)
except Exception as e:
    print(f"RED: compile_to_claim module failed to import: {e}")
    sys.exit(1)

from recurvelib.adapters.proxy.dyadic_lyapunov import Candidate

candidate = Candidate(N=3, b=(1.0, 2.0, 4.0, 8.0), d=(0.0, 0.0, 0.0))
draft = mod.compile_to_claim(candidate, nu=1.0, alpha=0.5)


def run_lean(body: str) -> subprocess.CompletedProcess:
    full = (
        "import NavierStokes.Shells.Basic\n\n"
        "namespace NavierStokes.Shells\n\n"
        f"{body}\n"
        "end NavierStokes.Shells\n\n"
        "open NavierStokes.Shells\n\n"
        f"{draft.statement_lean}\n"
    )
    with tempfile.TemporaryDirectory() as tmp:
        lean_file = Path(tmp) / "Check.lean"
        lean_file.write_text(full)
        return subprocess.run(
            ["lake", "env", "lean", str(lean_file)],
            cwd=ns_repo, capture_output=True, text=True, timeout=120,
        )


def first_error(proc: subprocess.CompletedProcess) -> str:
    for line in (proc.stdout + proc.stderr).splitlines():
        if "error" in line.lower():
            return line.strip()[:200]
    return "(no error line found)"


real = run_lean(draft.theorem_lean)
if real.returncode != 0:
    print(f"RED: the real compiled claim did not elaborate against the sibling repo: "
          f"{first_error(real)}")
    sys.exit(1)
if "sorryAx" in real.stdout or "sorryAx" in real.stderr:
    print("RED: the real compiled claim's proof depends on sorryAx")
    sys.exit(1)

trapped = run_lean(draft.trap_lean)
if trapped.returncode == 0:
    print("RED: compile_to_claim's own trap (the impostor theorem) elaborated instead of "
          "being rejected — a fooled proxy candidate would slip through")
    sys.exit(1)

print("GREEN: compile_to_claim's output elaborates and is kernel-clean against the real "
      "sibling gate; its own trap is correctly rejected")
sys.exit(0)
PYEOF

#!/usr/bin/env bash
# AB-15: adding an adapter never touches the loop — the grep-based fixture
# (docs/plans/ablation-infra.md AI2's own named counterexample, repeated in
# §8's acceptance list). RED-first: until a trivial new adapter can be
# added with a zero-diff runtime.py/controller.py, the probe is RED.
#
# Adds a REAL, throwaway, test-only "echo" adversary to a temp CLONE of this
# repo (never the real working tree — a probe must not mutate sacred
# space), registers it with one line, and asserts `git diff` against
# runtime.py/controller.py is empty.
#
# With $TRAP_FIXTURE: a scenario where the "trivial adapter" is added by
# ALSO touching controller.py (e.g. a naive implementation that hardcodes a
# new decide() branch instead of composing through the existing
# governor_status parameter). The real requirement must catch this (RED).
set -u
ROOT="$(cd "$(dirname "$0")/../../../.." && pwd)"
command -v git >/dev/null || { echo "git unavailable"; exit 2; }

T="$(mktemp -d)"; trap 'rm -rf "$T"' EXIT
CLONE="$T/clone"
git clone -q --no-hardlinks "$ROOT" "$CLONE" 2>&1 | grep -v "warning: " || true
cd "$CLONE"
EMPTY_HOOKS="$(mktemp -d)"
git config core.hooksPath "$EMPTY_HOOKS"
git config commit.gpgsign false
git config user.name t
git config user.email t@t

fail() { echo "FAIL: $1"; exit 1; }

ECHO_ADAPTER="recurvelib/adapters/adversary/echo_test_only.py"
INIT_FILE="recurvelib/adapters/adversary/__init__.py"

add_echo_adapter() {
  cat > "$ECHO_ADAPTER" <<'PY'
"""echo_test_only: a deliberately trivial adversary, added purely to prove
adding adapter N+1 never touches the loop, the controller, or decide()
(docs/plans/ablation-infra.md AI2). Test-only; not part of any real config
surface.
"""
from __future__ import annotations

from recurvelib.loop.reviewers import AdversaryVerdict


class EchoAdversary:
    """Always agrees — a no-op with a distinct name from `off`, so its
    presence in the registry is unambiguous."""

    def review(self, claim) -> AdversaryVerdict:
        return AdversaryVerdict.no_objection()
PY
  python3 - "$INIT_FILE" <<'PY'
import sys
path = sys.argv[1]
text = open(path).read()
text = text.replace(
    "from recurvelib.adapters.adversary.cross_model import CrossModelAdversary\n",
    "from recurvelib.adapters.adversary.cross_model import CrossModelAdversary\n"
    "from recurvelib.adapters.adversary.echo_test_only import EchoAdversary\n",
)
text = text.replace(
    '    "cross_model": CrossModelAdversary,\n})',
    '    "cross_model": CrossModelAdversary,\n    "echo_test_only": EchoAdversary,\n})',
)
open(path, "w").write(text)
PY
}

if [ -n "${TRAP_FIXTURE:-}" ]; then
  scenario="$(cat "$TRAP_FIXTURE/scenario" 2>/dev/null || echo "")"
  if [ "$scenario" != "trivial_adapter_touches_controller" ]; then
    echo "unknown scenario: $scenario"; exit 2
  fi
  # A "trivial adapter" added the WRONG way: it hardcodes a bespoke branch
  # directly into controller.py instead of composing through the existing
  # Adversary port + registry — exactly what AI2 forbids.
  add_echo_adapter
  python3 -c "
path = 'recurvelib/loop/controller.py'
text = open(path).read()
text = text.replace(
    'GOVERNOR_STATUSES = (\"off\", \"cleared\", \"pending\", \"vetoed\")',
    'GOVERNOR_STATUSES = (\"off\", \"cleared\", \"pending\", \"vetoed\")\n'
    '_ECHO_ADAPTER_HACK = True  # a bad adapter addition touching the controller directly',
)
open(path, 'w').write(text)
"
  DIFF_HIT="$(git diff --name-only -- recurvelib/loop/runtime.py recurvelib/loop/controller.py)"
  if [ -z "$DIFF_HIT" ]; then
    echo "ours=no diff detected oracle=controller.py was touched — the grep-based fixture "\
         "failed to catch it (fixture's gaming attempt succeeded)"
    exit 0
  fi
  echo "ours=git diff against runtime.py/controller.py is non-empty ($DIFF_HIT) "\
       "oracle=must be empty — correctly caught the loop-touching adapter"
  exit 1
fi

# --- no TRAP_FIXTURE: the real positive assertions -------------------------

BEFORE_RUNTIME="$(git rev-parse HEAD:recurvelib/loop/runtime.py)"
BEFORE_CONTROLLER="$(git rev-parse HEAD:recurvelib/loop/controller.py)"

add_echo_adapter

# 1. runtime.py and controller.py show ZERO diff — the actual grep-based
# fixture AI2 names.
DIFF_HIT="$(git diff --name-only -- recurvelib/loop/runtime.py recurvelib/loop/controller.py)"
[ -z "$DIFF_HIT" ] || fail "adding the trivial adapter touched: $DIFF_HIT"
AFTER_RUNTIME="$(git hash-object recurvelib/loop/runtime.py)"
AFTER_CONTROLLER="$(git hash-object recurvelib/loop/controller.py)"
[ "$BEFORE_RUNTIME" = "$AFTER_RUNTIME" ] || fail "runtime.py content hash changed"
[ "$BEFORE_CONTROLLER" = "$AFTER_CONTROLLER" ] || fail "controller.py content hash changed"

# 2. the footprint is genuinely minimal: exactly the new adapter file plus
# one registry-file edit, nothing else.
CHANGED="$(git diff --name-only; git ls-files --others --exclude-standard)"
NCHANGED="$(echo "$CHANGED" | grep -c . || true)"
[ "$NCHANGED" = "2" ] || fail "expected exactly 2 changed/new files, got $NCHANGED: $CHANGED"
echo "$CHANGED" | grep -qx "$INIT_FILE" || fail "registry file not among the changes"
echo "$CHANGED" | grep -qx "$ECHO_ADAPTER" || fail "new adapter file not among the changes"

# 3. the addition is REAL and functioning, not just an empty file — it
# actually resolves through the registry and works.
RESULT="$(python3 -c "
import sys
sys.path.insert(0, '.')
from recurvelib.adapters.adversary import ADVERSARY_ADAPTERS
from recurvelib.adapters.registry import resolve_adversary
cls = resolve_adversary('echo_test_only', ADVERSARY_ADAPTERS)
v = cls().review(None)
print('ok' if v.is_clean else 'not-clean')
")"
[ "$RESULT" = "ok" ] || fail "the new adapter does not resolve/work: $RESULT"

echo "adding a deliberately trivial new adapter (a real, registered, working EchoAdversary) "\
     "leaves runtime.py and controller.py byte-identical — zero diff, zero content-hash "\
     "change — with a genuinely minimal two-file footprint"
exit 0

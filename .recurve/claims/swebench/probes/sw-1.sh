#!/usr/bin/env bash
# SW-1: the environment image is built via SWE-bench's OWN instance-building
# tooling (make_test_spec + build_instance_image — pip install swebench),
# pinned by digest; we own the pin+reconciliation, not the construction.
#
# RED-first: before evallib/swebench_env.py existed, there was no
# `reconcile_test_collection` to compare a built environment's test
# collection against the officially-documented one — any hand-rolled build
# (missing an environment-setup step) would silently pin a divergent image.
#
# With $TRAP_FIXTURE: a reconciliation that compares test-collection COUNT
# instead of IDENTITY — a plausible bug that misses a build which drops one
# test and picks up a different one at the same total count. The real
# requirement must catch this: comparing SETS of node ids, not counts.
set -u
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$DIR/../../../.." && pwd)"
EVAL="$REPO/eval"
command -v python3 >/dev/null || { echo "python3 unavailable"; exit 2; }

FIXTURES='
OFFICIAL = """tests/test_blueprints.py::test_dotted_name_not_allowed
tests/test_blueprints.py::test_empty_name_not_allowed
tests/test_blueprints.py::test_dotted_names_from_app
3 tests collected in 0.12s"""

# A build missing an environment-setup step: it drops test_empty_name_not_allowed
# (the fixture never got the dependency it needs to collect) but picks up an
# UNRELATED test at the same position — same COUNT, different SET.
DIVERGENT_SAME_COUNT = """tests/test_blueprints.py::test_dotted_name_not_allowed
tests/test_blueprints.py::test_unrelated_leftover_from_stale_cache
tests/test_blueprints.py::test_dotted_names_from_app
3 tests collected in 0.11s"""
'

if [ -n "${TRAP_FIXTURE:-}" ]; then
  [ -f "$TRAP_FIXTURE/broken_reconcile.py" ] || { echo "trap fixture missing broken_reconcile.py"; exit 2; }
  out="$(EVAL="$EVAL" python3 -c "
import sys; sys.path.insert(0, '$EVAL')
$FIXTURES
import importlib.util
spec = importlib.util.spec_from_file_location('broken_reconcile', '$TRAP_FIXTURE/broken_reconcile.py')
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
try:
    result = mod.reconcile_test_collection(DIVERGENT_SAME_COUNT, OFFICIAL)
    print('ACCEPTED:' + result)
except mod.TestCollectionMismatch as e:
    print('REJECTED')
" 2>&1)" || { echo "trap harness could not run: $out"; exit 2; }
  case "$out" in
    ACCEPTED:match)
      echo "ours=count-only reconciliation silently accepted a same-count, "\
           "different-identity build oracle=must raise TestCollectionMismatch — "\
           "correctly caught the count-only comparison bug"
      exit 1 ;;
    REJECTED)
      echo "ours=broken_reconcile unexpectedly rejected the divergent build "\
           "oracle=the fixture failed to exercise the count-only bug"
      exit 0 ;;
    *) echo "trap scenario produced unexpected output: $out"; exit 2 ;;
  esac
fi

# --- no TRAP_FIXTURE: the real positive assertions -------------------------

out="$(EVAL="$EVAL" python3 -c "
import sys; sys.path.insert(0, '$EVAL')
$FIXTURES
try:
    from evallib.swebench_env import (
        reconcile_test_collection, parse_collected_tests, environment_image_hash,
        missing_image_remediation, TestCollectionMismatch,
    )
except Exception as e:
    print('MISSING', e); raise SystemExit(0)

# 1. identical collections match.
assert reconcile_test_collection(OFFICIAL, OFFICIAL) == 'match'

# 2. a build missing a test (dependency/env-setup gap) is caught by IDENTITY,
# not count — the same total, different set, must still raise.
try:
    reconcile_test_collection(DIVERGENT_SAME_COUNT, OFFICIAL)
    raise AssertionError('same-count divergent build was NOT caught')
except TestCollectionMismatch as e:
    assert 'test_empty_name_not_allowed' in str(e), str(e)

# 3. parse_collected_tests extracts exactly the node ids, ignoring the summary line.
ids = parse_collected_tests(OFFICIAL)
assert ids == {
    'tests/test_blueprints.py::test_dotted_name_not_allowed',
    'tests/test_blueprints.py::test_empty_name_not_allowed',
    'tests/test_blueprints.py::test_dotted_names_from_app',
}, ids

# 4. the pin is per-instance: same digest, different instance_id/base_commit
# -> different hash (SW4 keys calibration off THIS, not one global hash).
lock_a = {'instance_id': 'pallets__flask-5014', 'repo': 'pallets/flask',
          'base_commit': 'abc', 'digest': 'sha256:x', 'platform': 'linux/x86_64', 'host': 'h'}
lock_b = dict(lock_a, instance_id='django__django-9999', base_commit='zzz')
assert environment_image_hash(lock_a) != environment_image_hash(lock_b)
assert environment_image_hash(lock_a) == environment_image_hash(dict(lock_a))  # stable

# 5. a missing image names the one-command remediation (fresh-clone reachability).
msg = missing_image_remediation('pallets__flask-5014', 'sha256:x')
assert 'eval swebench build' in msg and 'pallets__flask-5014' in msg, msg

print('OK')
" 2>&1)"
printf '%s\n' "$out" | grep -q '^OK$' || { echo "ours=SW1 reconciliation wrong: $(printf '%s' "$out"|tail -1) oracle=environment image built via swebench's own tooling, pinned+reconciled by test-collection identity"; exit 1; }
echo "environment image built via SWE-bench's own instance-building tooling; pinned by a per-instance digest hash; reconciliation catches a same-count, divergent-identity hand-rolled build"
exit 0

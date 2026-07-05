#!/usr/bin/env bash
# SW-5: warm container reuse is per-instance, not per-run. BigCodeBench's
# WarmOracle keeps ONE container warm for the whole run (one shared oracle
# image); SWE-bench has no such shared image, so warm reuse is scoped to ONE
# instance's own 3 oracle-verification runs — `PerInstanceWarmRegistry`
# reuses `WarmOracle` unchanged for exactly that scope, and refuses to grade
# a DIFFERENT instance under a stale warm container.
#
# RED-first: before evallib/swebench_warm.py existed, there was no
# per-instance scoping concept at all — `WarmOracle` alone has no notion of
# "which instance this container belongs to".
#
# With $TRAP_FIXTURE: a registry that grades under WHATEVER container is
# currently warm, with no instance check at all — silently grading a
# different instance's workload in the wrong environment.
set -u
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$DIR/../../../.." && pwd)"
EVAL="$REPO/eval"
command -v python3 >/dev/null || { echo "python3 unavailable"; exit 2; }

FIXTURE_RUN='
def fake_run(cmd, timeout=None):
    if cmd[:2] == ["docker", "run"]:
        return 0, "cid-fixed\n"
    if cmd[:2] == ["docker", "inspect"]:
        return 0, "sha256:AAA\n"
    if cmd[:2] == ["docker", "exec"]:
        return 0, "ok-from-whatever-is-warm\n"
    if cmd[:2] == ["docker", "rm"]:
        return 0, ""
    return 0, ""
'

if [ -n "${TRAP_FIXTURE:-}" ]; then
  [ -f "$TRAP_FIXTURE/broken_registry.py" ] || { echo "trap fixture missing broken_registry.py"; exit 2; }
  out="$(EVAL="$EVAL" python3 -c "
import sys; sys.path.insert(0, '$EVAL')
$FIXTURE_RUN
from evallib.warm_oracle import WarmOracle
import importlib.util
spec = importlib.util.spec_from_file_location('broken_registry', '$TRAP_FIXTURE/broken_registry.py')
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

warm = WarmOracle('sha256:AAA', '/tmp/base', run=fake_run)
warm.start()
reg = mod.BrokenWarmRegistry(warm)  # warm for instance-A
try:
    rc, out = reg.grade('instance-B', '/tmp/base/w2', ['-m', 'x'], timeout=5)
    print('GRADED_UNDER_WRONG_INSTANCE')
except mod.WrongInstanceError:
    print('REFUSED')
" 2>&1)" || { echo "trap harness could not run: $out"; exit 2; }
  case "$out" in
    GRADED_UNDER_WRONG_INSTANCE)
      echo "ours=registry graded instance-B under instance-A's warm container, "\
           "no check at all oracle=must raise WrongInstanceError — correctly caught the missing guard"
      exit 1 ;;
    REFUSED)
      echo "ours=broken_registry unexpectedly refused oracle=the fixture failed to exercise the missing-guard bug"
      exit 0 ;;
    *) echo "trap scenario produced unexpected output: $out"; exit 2 ;;
  esac
fi

# --- no TRAP_FIXTURE: the real positive assertions -------------------------

out="$(EVAL="$EVAL" python3 -c "
import sys; sys.path.insert(0, '$EVAL')
$FIXTURE_RUN
try:
    from evallib.swebench_warm import PerInstanceWarmRegistry, WrongInstanceError
except Exception as e:
    print('MISSING', e); raise SystemExit(0)

reg = PerInstanceWarmRegistry(run=fake_run)

# 1. warm_for(instance-A) then grade(instance-A) works.
reg.warm_for('instance-A', 'sha256:AAA', '/tmp/base')
rc, out = reg.grade('instance-A', '/tmp/base/w1', ['-m', 'x'], timeout=5)
assert rc == 0 and 'ok' in out, (rc, out)

# 2. grading instance-B while instance-A's container is still warm is REFUSED
# -- never silently grades under the wrong environment.
try:
    reg.grade('instance-B', '/tmp/base/w2', ['-m', 'x'], timeout=5)
    raise AssertionError('cross-instance grade was NOT refused')
except WrongInstanceError:
    pass

# 3. warm_for(instance-B) switches (stopping instance-A's container, counted),
# then grading instance-B works -- the per-instance cost is real, not eliminated.
before = reg.instance_switches
reg.warm_for('instance-B', 'sha256:AAA', '/tmp/base')
assert reg.instance_switches == before + 1
rc, out = reg.grade('instance-B', '/tmp/base/w2', ['-m', 'x'], timeout=5)
assert rc == 0, (rc, out)

# 4. re-warming the SAME instance+digest reuses the existing container (no
# extra switch) -- the amortization this requirement exists to keep.
before = reg.instance_switches
reg.warm_for('instance-B', 'sha256:AAA', '/tmp/base')
assert reg.instance_switches == before, 'reusing the same instance should not count as a switch'

reg.stop()
print('OK')
" 2>&1)"
printf '%s\n' "$out" | grep -q '^OK$' || { echo "ours=SW5 warm reuse wrong: $(printf '%s' "$out"|tail -1) oracle=warm containers reused within one instance's own runs, never across a different instance"; exit 1; }
echo "warm container reuse is scoped per-instance (WarmOracle reused unchanged); grading a different instance under a stale warm container is refused, not silently run"
exit 0

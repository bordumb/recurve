#!/usr/bin/env bash
# SW-3: oracle quarantine — a fresh instance, the diff, and nothing else.
# Grading applies the agent's EXTRACTED DIFF ONLY (never the container
# itself) to a fresh copy of the environment image + test_patch, network
# disabled. `refuse_reuse_of_agent_container` is the enforcement: grading
# against the agent's own container id is refused before a single test runs.
#
# RED-first: before evallib/swebench_quarantine.py existed, there was no
# guard preventing a grading pass from running inside the agent's own live
# container — the exact state-leakage quarantine exists to prevent.
#
# With $TRAP_FIXTURE: a "reuse guard" that never actually refuses anything
# (skips the check entirely) — the real requirement must catch this: grading
# against the agent's own container id must be refused.
set -u
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$DIR/../../../.." && pwd)"
EVAL="$REPO/eval"
command -v python3 >/dev/null || { echo "python3 unavailable"; exit 2; }

if [ -n "${TRAP_FIXTURE:-}" ]; then
  [ -f "$TRAP_FIXTURE/broken_refuse_reuse.py" ] || { echo "trap fixture missing broken_refuse_reuse.py"; exit 2; }
  out="$(EVAL="$EVAL" python3 -c "
import sys; sys.path.insert(0, '$EVAL')
import importlib.util
spec = importlib.util.spec_from_file_location('broken_refuse_reuse', '$TRAP_FIXTURE/broken_refuse_reuse.py')
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
# The scenario a real grade_fresh must refuse: the grading container id IS the
# agent's own — state leakage into its own grade.
try:
    mod.refuse_reuse_of_agent_container('shared-container-1', 'shared-container-1')
    print('ACCEPTED_SELF_GRADE')
except mod.OracleContainerReuseError:
    print('REJECTED_SELF_GRADE')
" 2>&1)" || { echo "trap harness could not run: $out"; exit 2; }
  case "$out" in
    ACCEPTED_SELF_GRADE)
      echo "ours=broken reuse guard let grading run against the agent's own "\
           "container oracle=must raise OracleContainerReuseError — correctly caught the missing-guard bug"
      exit 1 ;;
    REJECTED_SELF_GRADE)
      echo "ours=broken_refuse_reuse unexpectedly refused oracle=the fixture failed to exercise the missing-guard bug"
      exit 0 ;;
    *) echo "trap scenario produced unexpected output: $out"; exit 2 ;;
  esac
fi

# --- no TRAP_FIXTURE: the real positive assertions -------------------------

out="$(EVAL="$EVAL" python3 -c "
import sys; sys.path.insert(0, '$EVAL')
try:
    from evallib.swebench_quarantine import (
        refuse_reuse_of_agent_container, OracleContainerReuseError, build_report_from_log,
    )
except Exception as e:
    print('MISSING', e); raise SystemExit(0)

# 1. different ids -> no raise (a genuinely fresh grading container is fine).
refuse_reuse_of_agent_container('agent-container-1', 'fresh-container-2')

# 2. the SAME id (grading would run inside the agent's own container) -> refused.
try:
    refuse_reuse_of_agent_container('shared-container-1', 'shared-container-1')
    raise AssertionError('same-id reuse was NOT refused')
except OracleContainerReuseError:
    pass

# 3. no fresh container at all (None/empty grading id) -> refused; 'no isolation
# happened' must never read as 'safe because nothing to compare against'.
try:
    refuse_reuse_of_agent_container('agent-container-1', None)
    raise AssertionError('missing grading container id was NOT refused')
except OracleContainerReuseError:
    pass
try:
    refuse_reuse_of_agent_container(None, '')
    raise AssertionError('empty grading container id was NOT refused')
except OracleContainerReuseError:
    pass

# 4. build_report_from_log is a pass-through to SWE-bench's OWN get_eval_report
# (reused, not reimplemented) -- surface check only (docker path is oracle-waived).
import inspect
src = inspect.getsource(build_report_from_log)
assert 'get_eval_report' in src, src

print('OK')
" 2>&1)"
printf '%s\n' "$out" | grep -q '^OK$' || { echo "ours=SW3 quarantine wrong: $(printf '%s' "$out"|tail -1) oracle=grading refuses the agent's own container, always a fresh one"; exit 1; }
echo "grading refuses to run against the agent's own container id (or an absent/empty one); get_eval_report reused from SWE-bench's own harness, never reimplemented"
exit 0

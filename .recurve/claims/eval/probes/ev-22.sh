#!/usr/bin/env bash
# EV-22 (O4): paid-run grading may parallelize (the timeout is already calibrated,
# so grading timings no longer derive anything) — but under a DECLARED concurrency
# recorded in the lock, with two protections so speed never corrupts a verdict:
#   (a) a grading that TIMES OUT is retried once SERIALLY before it is scored —
#       contention-induced slowness must be given a contention-free attempt, so it
#       is not misrecorded as an oracle error (an error inflates the headline);
#   (b) the concurrency actually used must equal the concurrency in the lock, else
#       refuse — the run cannot silently grade under a concurrency the calibration
#       did not account for.
# The serial retry fires on a TIMEOUT only, never on a genuine test failure.
# Hermetic: the grade backend is injected; no docker.
#
# RED until grade_policy exists. Traps: a contention timeout scored as an error
# instead of retried; a concurrency mismatch (used != locked) accepted.
set -u
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$DIR/../../../.." && pwd)"
EVAL="$REPO/eval"
command -v python3 >/dev/null || { echo "python3 unavailable"; exit 2; }

HELP='
import os, sys, threading; sys.path.insert(0, os.environ["EVAL"])
from evallib.grade_policy import (assert_concurrency_matches, serial_retry_on_timeout,
                                  ConcurrencyMismatch)
def flaky(seq):
    """A grade backend returning the given (rc, out) per successive call."""
    st={"i":0}
    def g(workdir, argv, timeout):
        r=seq[min(st["i"], len(seq)-1)]; st["i"]+=1; return r
    g.calls=st
    return g
'

if [ -n "${TRAP_FIXTURE:-}" ]; then
  [ -f "$TRAP_FIXTURE/claims" ] || { echo "trap fixture missing claims file"; exit 2; }
  scenario="$(cat "$TRAP_FIXTURE/scenario" 2>/dev/null || echo contention_scored_error)"
  out="$(EVAL="$EVAL" python3 -c "
$HELP
sc='$scenario'
if sc=='contention_scored_error':
    g=flaky([(124,'TIMEOUT'), (0,'ok')])           # times out under load, passes on serial retry
    w=serial_retry_on_timeout(g, threading.Lock())
    rc,out=w('d',['x'],1)
    print('RETRIED' if rc==0 else 'SCORED_ERROR')
elif sc=='concurrency_mismatch':
    try: assert_concurrency_matches(4, 2); print('ACCEPTED')
    except ConcurrencyMismatch: print('REFUSED')
" 2>&1)" || { echo "grade_policy incomplete: $out"; exit 2; }
  case "$scenario:$out" in
    contention_scored_error:RETRIED) echo "a contention timeout is retried serially, not scored as an error"; exit 1 ;;
    concurrency_mismatch:REFUSED)    echo "a concurrency mismatch (used != locked) is refused"; exit 1 ;;
    *) echo "grade_policy failed the '$scenario' guard: $out (fixture claimed it does)"; exit 0 ;;
  esac
fi

out="$(EVAL="$EVAL" python3 -c "
$HELP
try:
    pass
except Exception as e:
    print('MISSING', e); raise SystemExit(0)

# concurrency must match the lock
assert_concurrency_matches(2, 2)   # no raise
for used, locked in [(4,2),(1,2),(0,1)]:
    try: assert_concurrency_matches(used, locked); raise SystemExit(f'mismatch {used}!={locked} accepted')
    except ConcurrencyMismatch: pass

# (a) a contention timeout (passes on the serial retry) is scored by the retry, not as error
g=flaky([(124,'TIMEOUT'), (0,'ok')])
w=serial_retry_on_timeout(g, threading.Lock())
rc,out=w('d',['x'],1); assert rc==0, ('contention timeout not rescued', rc)
assert g.calls['i']==2, ('serial retry did not fire', g.calls['i'])

# a GENUINE timeout (times out even serially) stays a timeout — bounded to ONE retry
g2=flaky([(124,'TIMEOUT'), (124,'TIMEOUT')])
w2=serial_retry_on_timeout(g2, threading.Lock())
rc,out=w2('d',['x'],1); assert rc==124, ('genuine timeout masked', rc)
assert g2.calls['i']==2, ('retried more than once', g2.calls['i'])

# a genuine FAILURE is never retried — the serial retry is for timeouts only
g3=flaky([(1,'FAILED (failures=1)')])
w3=serial_retry_on_timeout(g3, threading.Lock())
rc,out=w3('d',['x'],1); assert rc==1 and g3.calls['i']==1, ('a real failure was retried', g3.calls['i'])

# the retry runs under the given serial lock (held during the retry)
held={'v':False}
class L:
    def __enter__(self): held['v']=True; return self
    def __exit__(self,*a): pass
g4=flaky([(124,'TIMEOUT'), (0,'ok')])
serial_retry_on_timeout(g4, L())('d',['x'],1)
assert held['v'], 'retry did not acquire the serial lock'

# WIRED: cmd_run enforces the concurrency match and wraps grading with the retry
import inspect
from evallib import cli
src=inspect.getsource(cli.cmd_run)
assert 'assert_concurrency_matches' in src, 'cmd_run does not enforce the lock concurrency'
assert 'serial_retry_on_timeout' in src, 'cmd_run does not wrap grading with the serial retry'
print('OK')
" 2>&1)"
printf '%s\n' "$out" | grep -q '^OK$' || { echo "ours=grade_policy wrong: $(printf '%s' "$out"|tail -1) oracle=concurrency matches lock, timeout->one serial retry, failures never retried"; exit 1; }
echo "grading concurrency: matches the lock, a timeout gets one serial retry (contention != error), a failure is never retried"
exit 0

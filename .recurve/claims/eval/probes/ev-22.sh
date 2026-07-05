#!/usr/bin/env bash
# EV-22 (O4): paid-run grading may parallelize (the timeout is calibrated, so
# grading timings no longer derive anything) — under a concurrency DECLARED in the
# lock, with two protections so speed never corrupts a verdict:
#   (a) a grading that TIMES OUT is retried once, and the retry runs GENUINELY
#       EXCLUSIVE — normal grades hold a READ lock, the retry takes the WRITE lock
#       and drains all in-flight gradings, so a contention-slowed but valid grade
#       gets a truly contention-free attempt instead of being misrecorded as an
#       oracle error. (A "calmer" retry that only serializes retries against each
#       other is not enough — at high concurrency the slow grade times out again
#       and is scored an error, the exact headline-inflating failure O4 prevents.
#       Because the retry is genuinely verdict-independent, grade_concurrency may
#       live in the lock but OUTSIDE the identity — bumping it needs no recalibrate.)
#   (b) the concurrency actually used must equal the lock's grade_concurrency.
# The retry fires on a TIMEOUT ONLY (rc==124), never on a genuine failure whose
# output merely mentions "timeout"; it is bounded to one retry.
# Hermetic: the grade backend is injected; no docker.
#
# RED until grade_policy has a real RW lock + strict sentinel. Traps: a retry that
# runs while a reader is in flight (not exclusive); a contention timeout scored as
# an error; a concurrency mismatch accepted.
set -u
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$DIR/../../../.." && pwd)"
EVAL="$REPO/eval"
command -v python3 >/dev/null || { echo "python3 unavailable"; exit 2; }

HELP='
import os, sys, threading; sys.path.insert(0, os.environ["EVAL"])
from evallib.grade_policy import (assert_concurrency_matches, serial_retry_on_timeout,
                                  ConcurrencyMismatch, RWLock)
def flaky(seq):
    st={"i":0}
    def g(workdir, argv, timeout):
        r=seq[min(st["i"], len(seq)-1)]; st["i"]+=1; return r
    g.calls=st
    return g
def exclusivity_probe():
    """A reader holds the RW lock; a writer (retry) must block until it drains."""
    rw=RWLock(); wrote=threading.Event()
    rw.acquire_read()
    t=threading.Thread(target=lambda:(rw.acquire_write(), wrote.set(), rw.release_write()))
    t.start()
    blocked = not wrote.wait(0.3)          # writer must NOT acquire while a reader holds
    rw.release_read()
    got = wrote.wait(2)                     # ...and must acquire once readers drain
    t.join(2)
    return blocked, got
'

if [ -n "${TRAP_FIXTURE:-}" ]; then
  [ -f "$TRAP_FIXTURE/claims" ] || { echo "trap fixture missing claims file"; exit 2; }
  scenario="$(cat "$TRAP_FIXTURE/scenario" 2>/dev/null || echo retry_not_exclusive)"
  out="$(EVAL="$EVAL" python3 -c "
$HELP
sc='$scenario'
if sc=='retry_not_exclusive':
    blocked, got = exclusivity_probe()
    print('EXCLUSIVE' if (blocked and got) else 'NOT_EXCLUSIVE')
elif sc=='contention_scored_error':
    g=flaky([(124,'TIMEOUT'), (0,'ok')])
    w=serial_retry_on_timeout(g, RWLock()); rc,out=w('d',['x'],1)
    print('RETRIED' if rc==0 else 'SCORED_ERROR')
elif sc=='concurrency_mismatch':
    try: assert_concurrency_matches(4, 2); print('ACCEPTED')
    except ConcurrencyMismatch: print('REFUSED')
" 2>&1)" || { echo "grade_policy incomplete: $out"; exit 2; }
  case "$scenario:$out" in
    retry_not_exclusive:EXCLUSIVE)   echo "the retry runs genuinely exclusive (drains in-flight readers)"; exit 1 ;;
    contention_scored_error:RETRIED) echo "a contention timeout is retried, not scored an error"; exit 1 ;;
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
assert_concurrency_matches(2, 2)
for used, locked in [(4,2),(1,2),(0,1)]:
    try: assert_concurrency_matches(used, locked); raise SystemExit(f'mismatch {used}!={locked} accepted')
    except ConcurrencyMismatch: pass

# (a) the retry is GENUINELY exclusive: a writer blocks while a reader is in flight,
#     then proceeds once readers drain
blocked, got = exclusivity_probe()
assert blocked, 'the retry acquired the lock while a normal grade was in flight — not contention-free'
assert got, 'the retry never acquired after the reader drained'

# a contention timeout (passes on the exclusive retry) is scored by the retry, not as error
g=flaky([(124,'TIMEOUT'), (0,'ok')])
w=serial_retry_on_timeout(g, RWLock()); rc,out=w('d',['x'],1)
assert rc==0 and g.calls['i']==2, ('contention timeout not rescued', rc, g.calls['i'])

# a GENUINE timeout stays a timeout — bounded to ONE retry
g2=flaky([(124,'TIMEOUT'), (124,'TIMEOUT')])
rc,out=serial_retry_on_timeout(g2, RWLock())('d',['x'],1)
assert rc==124 and g2.calls['i']==2, ('genuine timeout masked or over-retried', rc, g2.calls['i'])

# STRICT sentinel: a genuine FAILURE whose output merely mentions timeout is NOT retried
g3=flaky([(1,'FAILED (failures=1): connection TIMEOUT in test')])
rc,out=serial_retry_on_timeout(g3, RWLock())('d',['x'],1)
assert rc==1 and g3.calls['i']==1, ('a real failure mentioning timeout was wastefully retried', g3.calls['i'])

# WIRED: cmd_run enforces the concurrency match and wraps grading with the exclusive retry
import inspect
from evallib import cli
src=inspect.getsource(cli.cmd_run)
assert 'assert_concurrency_matches' in src, 'cmd_run does not enforce the lock concurrency'
assert 'serial_retry_on_timeout' in src and 'RWLock' in src, 'cmd_run does not wrap grading with the exclusive retry'
print('OK')
" 2>&1)"
printf '%s\n' "$out" | grep -q '^OK$' || { echo "ours=grade_policy wrong: $(printf '%s' "$out"|tail -1) oracle=RW-exclusive retry, rc==124-only sentinel, concurrency matches lock"; exit 1; }
echo "grading concurrency: matches the lock; a timeout gets ONE genuinely-exclusive serial retry (rc==124 only); a failure is never retried"
exit 0

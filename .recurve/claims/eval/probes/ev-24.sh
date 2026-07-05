#!/usr/bin/env bash
# EV-24: the harness bounds spend WITHOUT trusting the agent to police itself.
# `--max-budget-usd` is the agent's self-limit (layer 1), but a self-limit you
# cannot verify mid-session is not a bound — so `run_agent_capped` runs every
# agent invocation under a harness-side HARD-KILL watchdog (layer 2): a wall-clock
# backstop that SIGKILLs the whole process GROUP if the session overruns, so a
# runaway agent — and any children it spawned — is stopped dead, its pending work
# never completing, rather than left to bill unbounded. A well-behaved session
# completes untouched with its output captured. Hermetic (a shell stand-in, no
# agent).
#
# RED until run_agent_capped exists. Traps: a runaway session (with a child) run
# to completion instead of hard-killed; a fast, well-behaved session wrongly
# killed by an over-eager watchdog.
set -u
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$DIR/../../../.." && pwd)"
EVAL="$REPO/eval"
command -v python3 >/dev/null || { echo "python3 unavailable"; exit 2; }

HELP='
import os, sys, time, tempfile, pathlib; sys.path.insert(0, os.environ["EVAL"])
from evallib.watchdog import run_agent_capped
def marker():
    return str(pathlib.Path(tempfile.mkdtemp())/"done")
def runaway_with_child(m):
    # a child, backgrounded, that would touch the marker AFTER a delay — only a
    # process-GROUP kill stops it; killing just the parent lets the child survive
    return ["sh","-c", f"(sleep 2; touch {m}) & wait"]
'

if [ -n "${TRAP_FIXTURE:-}" ]; then
  [ -f "$TRAP_FIXTURE/claims" ] || { echo "trap fixture missing claims file"; exit 2; }
  scenario="$(cat "$TRAP_FIXTURE/scenario" 2>/dev/null || echo runaway_not_killed)"
  out="$(EVAL="$EVAL" python3 -c "
$HELP
sc='$scenario'
if sc=='runaway_not_killed':
    m=marker(); t0=time.time()
    r=run_agent_capped(runaway_with_child(m), '', wall_timeout=1)
    time.sleep(2.5)   # wait past when the child WOULD have touched the marker
    stopped = r['killed'] and (time.time()-t0 < 5) and not os.path.exists(m)
    print('KILLED' if stopped else 'SURVIVED')
elif sc=='wrongly_killed':
    r=run_agent_capped(['sh','-c','echo hi'], '', wall_timeout=5)
    print('SPARED' if (not r['killed'] and r['returncode']==0) else 'KILLED')
" 2>&1)" || { echo "watchdog incomplete: $out"; exit 2; }
  case "$scenario:$out" in
    runaway_not_killed:KILLED) echo "the watchdog hard-kills a runaway session and its children"; exit 1 ;;
    wrongly_killed:SPARED)     echo "a well-behaved session runs untouched"; exit 1 ;;
    *) echo "watchdog failed the '$scenario' guard: $out (fixture claimed it does)"; exit 0 ;;
  esac
fi

out="$(EVAL="$EVAL" python3 -c "
$HELP
try:
    pass
except Exception as e:
    print('MISSING', e); raise SystemExit(0)

# a well-behaved session completes, is not killed, and its output is captured
r=run_agent_capped(['sh','-c','echo hi'], '', wall_timeout=5)
assert r['killed'] is False and r['returncode']==0 and 'hi' in r['stdout'], r

# stdin is delivered to the session
r2=run_agent_capped(['sh','-c','cat'], 'PROMPT-IN', wall_timeout=5)
assert 'PROMPT-IN' in r2['stdout'], r2

# a runaway session is hard-killed, bounded near the wall_timeout (not the sleep),
# and the whole process GROUP dies — the backgrounded child never touches the marker
m=marker(); t0=time.time()
r3=run_agent_capped(runaway_with_child(m), '', wall_timeout=1)
elapsed=time.time()-t0
assert r3['killed'] is True, ('runaway not killed', r3)
assert elapsed < 5, ('kill not bounded near wall_timeout', elapsed)
time.sleep(2.5)   # past the child's delay
assert not os.path.exists(m), 'a child survived the kill (only the parent was killed, not the group)'
print('OK')
" 2>&1)"
printf '%s\n' "$out" | grep -q '^OK$' || { echo "ours=watchdog wrong: $(printf '%s' "$out"|tail -1) oracle=hard-kills a runaway group, spares a well-behaved session, delivers stdin"; exit 1; }
echo "watchdog: hard-kills a runaway session and its children near the wall_timeout, spares a well-behaved one, delivers stdin"
exit 0

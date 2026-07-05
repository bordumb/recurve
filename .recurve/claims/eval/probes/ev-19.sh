#!/usr/bin/env bash
# EV-19 (O1): the oracle grades in a WARM container — one start per run (or per
# worker), each grading a `docker exec`, not a fresh `docker run`. Under emulation
# the per-grading create/start/teardown costs ~1-2s against as little as 0.6s of
# work; the full run grades ~1,776 times, so container startup alone would be
# ~15-45 min. WarmOracle starts ONE container from the pinned digest, refuses to
# exec into a container whose image is not that digest (retag guard), gives each
# grading a fresh workdir (isolation, no cross-task reuse), and — if the warm
# container dies mid-run — restarts from the same digest, records it, and
# re-grades the interrupted task rather than emitting a silent error. The docker
# calls are injected, so the orchestration is hermetic; the real container is
# oracle-waived (verified live where docker is present).
#
# RED until WarmOracle exists. Traps: a grader that spawns one container per
# grading (starts > workers over a batch); a dead warm container that yields a
# silent error instead of a restart+re-grade; an exec into a mismatched image.
set -u
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$DIR/../../../.." && pwd)"
EVAL="$REPO/eval"
command -v python3 >/dev/null || { echo "python3 unavailable"; exit 2; }

HELP='
import os, sys, pathlib, tempfile; sys.path.insert(0, os.environ["EVAL"])
from evallib.warm_oracle import WarmOracle, OracleImageMismatch
DIGEST="sha256:pinned"
class Fake:
    """A recording fake docker runner. Modes flip behaviour for the trap probes."""
    def __init__(self, image=DIGEST, die_once=False):
        self.calls=[]; self.image=image; self.die_once=die_once; self._cid=0; self._alive=set()
    def __call__(self, cmd, timeout=None):
        self.calls.append(cmd)
        if cmd[:2]==["docker","run"]:
            self._cid+=1; cid=f"c{self._cid}"; self._alive.add(cid); return 0, cid+"\n"
        if cmd[:2]==["docker","inspect"]:
            return 0, self.image+"\n"               # the running container image
        if cmd[:2]==["docker","exec"]:
            cid=cmd[cmd.index("-w")+2] if "-w" in cmd else None
            execcid=[c for c in cmd if c.startswith("c")]
            cid=execcid[0] if execcid else None
            if self.die_once and cid in self._alive:
                self._alive.discard(cid); self.die_once=False
                return 1, f"Error response from daemon: Container {cid} is not running\n"
            return 0, "OK ... Ran 1 test ... ok\n"
        if cmd[:2]==["docker","rm"]:
            return 0, ""
        return 0, ""
    def starts(self): return sum(1 for c in self.calls if c[:2]==["docker","run"])
    def execs(self):  return sum(1 for c in self.calls if c[:2]==["docker","exec"])
def mkbase():
    b=pathlib.Path(tempfile.mkdtemp()); (b).mkdir(exist_ok=True); return b
def workdir(base):
    d=base/os.urandom(4).hex(); d.mkdir(); (d/"oracle_case.py").write_text("x"); return d
'

if [ -n "${TRAP_FIXTURE:-}" ]; then
  [ -f "$TRAP_FIXTURE/claims" ] || { echo "trap fixture missing claims file"; exit 2; }
  scenario="$(cat "$TRAP_FIXTURE/scenario" 2>/dev/null || echo per_grading_spawn)"
  out="$(EVAL="$EVAL" python3 -c "
$HELP
sc='$scenario'
if sc=='per_grading_spawn':
    f=Fake(); base=mkbase(); w=WarmOracle(DIGEST, base, run=f); w.start()
    for _ in range(10): w.grade(workdir(base), ['-m','unittest','oracle_case'])
    print('BOUNDED' if f.starts()<=1 else 'UNBOUNDED')
elif sc=='silent_error_on_death':
    f=Fake(die_once=True); base=mkbase(); w=WarmOracle(DIGEST, base, run=f); w.start()
    rc,out=w.grade(workdir(base), ['-m','unittest','oracle_case'])
    print('REGRADED' if (rc==0 and w.restarts>=1) else 'SILENT_ERROR')
elif sc=='mismatched_image':
    f=Fake(image='sha256:OTHER'); base=mkbase(); w=WarmOracle(DIGEST, base, run=f)
    try: w.start(); print('EXECUTED')
    except OracleImageMismatch: print('REFUSED')
" 2>&1)" || { echo "warm_oracle incomplete: $out"; exit 2; }
  case "$scenario:$out" in
    per_grading_spawn:BOUNDED)      echo "container starts are bounded by workers, not gradings"; exit 1 ;;
    silent_error_on_death:REGRADED) echo "a dead warm container is restarted and the task re-graded"; exit 1 ;;
    mismatched_image:REFUSED)       echo "exec into a mismatched-image container is refused"; exit 1 ;;
    *) echo "warm_oracle failed the '$scenario' guard: $out (fixture claimed it does)"; exit 0 ;;
  esac
fi

out="$(EVAL="$EVAL" python3 -c "
$HELP
try:
    pass
except Exception as e:
    print('MISSING', e); raise SystemExit(0)

# one start for a whole batch; one exec per grading
f=Fake(); base=mkbase(); w=WarmOracle(DIGEST, base, run=f); w.start()
for _ in range(10):
    rc,out=w.grade(workdir(base), ['-m','unittest','oracle_case']); assert rc==0, out
assert f.starts()==1, ('container started per grading', f.starts())
assert f.execs()==10, ('not one exec per grading', f.execs())

# isolation: each grading execs in its OWN workdir under the shared mount
seen=set()
for c in f.calls:
    if c[:2]==['docker','exec']:
        w_i=c.index('-w'); seen.add(c[w_i+1])
assert len(seen)==10, ('gradings reused a workdir', len(seen))
assert all(p.startswith('/work/') for p in seen), ('workdir not under the container mount', seen)

# the retag guard: the started container's image must equal the pinned digest
fbad=Fake(image='sha256:OTHER'); w2=WarmOracle(DIGEST, mkbase(), run=fbad)
try: w2.start(); raise SystemExit('mismatched image accepted')
except OracleImageMismatch: pass

# resilience: a mid-run death → restart from the same digest + re-grade, not a silent error
fdie=Fake(die_once=True); base3=mkbase(); w3=WarmOracle(DIGEST, base3, run=fdie); w3.start()
rc,out=w3.grade(workdir(base3), ['-m','unittest','oracle_case'])
assert rc==0 and w3.restarts>=1, ('dead container not restarted/re-graded', rc, w3.restarts)
# the restart used the pinned digest (a docker run referencing DIGEST happened after the death)
runs=[c for c in fdie.calls if c[:2]==['docker','run']]
assert all(DIGEST in c for c in runs), 'restart did not use the pinned digest'
print('OK')
" 2>&1)"
printf '%s\n' "$out" | grep -q '^OK$' || { echo "ours=warm_oracle wrong: $(printf '%s' "$out"|tail -1) oracle=one start per batch, exec per grade, fresh workdir, retag-refused, restart+regrade on death"; exit 1; }
echo "warm oracle: one container start per batch, docker exec per grading, fresh workdir, retag-refused, dead-container restart+re-grade"
exit 0

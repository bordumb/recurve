#!/usr/bin/env bash
# AK-5: AuditPort is additive-only — it can add columns to a row, never
# change declared_done/oracle_verdict. `AuditResult` is structurally
# incapable of carrying either field (a type-level guarantee, checked by
# `has_forbidden_field`, the same discipline recurvelib.loop.reviewers
# already applies to Adversary/Governor verdicts) — not a runtime check a
# future edit could quietly bypass. `drill_hardened` literally invokes the
# real, already-shipped `recurve drill --fuzz --iso --diff` CLI and parses
# its own real summary lines; A4 = A3 + this port.
#
# RED-first: before AuditPort existed there was no way to even name a
# hardening pass as part of an arm; A4 had no entry.
#
# With $TRAP_FIXTURE: a candidate AuditResult-like type that carries a
# `declared_done` field directly — the real requirement must flag it.
set -u
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$DIR/../../../.." && pwd)"
EVAL="$REPO/eval"
RECURVE="$REPO/recurve"
command -v python3 >/dev/null || { echo "python3 unavailable"; exit 2; }

if [ -n "${TRAP_FIXTURE:-}" ]; then
  scenario="$(cat "$TRAP_FIXTURE/scenario" 2>/dev/null || echo bypass_field_candidate)"
  out="$(python3 -c "
import sys, dataclasses
sys.path.insert(0, '$EVAL')
from evallib.audit import has_forbidden_field

if '$scenario' == 'bypass_field_candidate':
    @dataclasses.dataclass(frozen=True)
    class _BrokenAuditResult:
        audit_ran: bool = True
        declared_done: bool = True   # the bypass: smuggles the outcome directly
    hit = has_forbidden_field(_BrokenAuditResult)
    print('FLAGGED' if hit == 'declared_done' else 'NOT_FLAGGED')
else:
    print('UNKNOWN_SCENARIO')
" 2>&1)" || { echo "trap harness could not run: $out"; exit 2; }
  case "$out" in
    FLAGGED)
      echo "ours=has_forbidden_field correctly flags 'declared_done' on a candidate that smuggles "\
           "the outcome oracle=must flag — correctly caught"
      exit 1 ;;
    NOT_FLAGGED)
      echo "ours=no forbidden field flagged oracle=declared_done must be caught "\
           "(fixture's gaming candidate slipped through)"
      exit 0 ;;
    *) echo "trap scenario produced unexpected output: $out"; exit 2 ;;
  esac
fi

# --- no TRAP_FIXTURE: the real positive assertions -------------------------

out="$(python3 -c "
import sys, tempfile, subprocess, dataclasses
from pathlib import Path
sys.path.insert(0, '$EVAL')
try:
    from evallib.audit import AuditResult, has_forbidden_field, none_audit, drill_hardened_audit, \
        resolve_audit_port, AUDIT_PORTS
    from evallib.arms import arm_spec
except Exception as e:
    print('MISSING', e); raise SystemExit(0)

# 1. the real type carries neither forbidden field.
assert has_forbidden_field(AuditResult) is None, has_forbidden_field(AuditResult)

# 2. a candidate replacement type carrying either forbidden field IS flagged
# (the guard is reusable, not a one-off check of today's type).
@dataclasses.dataclass(frozen=True)
class _BadA:
    audit_ran: bool = True
    oracle_verdict: str = 'pass'
assert has_forbidden_field(_BadA) == 'oracle_verdict', has_forbidden_field(_BadA)

# 3. none_audit is the true no-op default.
r = none_audit(Path('.'))
assert r == AuditResult(audit_ran=False), r

# 4. drill_hardened genuinely invokes the real drill CLI against a real
# workspace with a REAL closed claim carrying a reference probe that
# disagrees — proving the parse against drill's own actual output, not a
# fabricated string.
ws = Path(tempfile.mkdtemp())
subprocess.run(['git', 'init', '-q'], cwd=ws, check=True)
subprocess.run(['python3', '$RECURVE', 'init'], cwd=ws, capture_output=True, text=True)
suite = ws / '.recurve' / 'claims' / 'core'
probes = suite / 'probes'
(probes / 'x-1.sh').write_text(
    '#!/usr/bin/env bash\nif [ -n \"\${TRAP_FIXTURE:-}\" ]; then echo bad; exit 1; fi\necho ok\nexit 0\n')
(probes / 'x-1.sh').chmod(0o755)
(probes / 'x-1.reference.sh').write_text('#!/usr/bin/env bash\necho disagrees\nexit 1\n')
(probes / 'x-1.reference.sh').chmod(0o755)
trap = probes / 'x-1.trap' / 'bad'; trap.mkdir(parents=True)
(trap / 'marker').write_text('bad-but-red')
(suite / 'gaps.yaml').write_text(
    '- id: X-1\n  title: fixture claim\n  class: missing-surface\n  status: closed\n'
    '  severity: feature\n  reads: none\n  evidence: [\"x:1\"]\n  observed: GREEN by construction\n'
    '  smallest_fix: none\n  probe: probes/x-1.sh\n  reference: probes/x-1.reference.sh\n')

audit = drill_hardened_audit(ws)
assert audit.audit_ran is True, audit
assert audit.diff_disagreements == 1, audit   # the real, planted disagreement
assert 'DISAGREEMENT' in audit.raw_output, audit
assert has_forbidden_field(type(audit)) is None

# 5. A4's exact port tuple; resolves through the SAME registry object.
a3, a4 = arm_spec('A3'), arm_spec('A4')
assert a4.workspace == a3.workspace and a4.done_signal == a3.done_signal, a4
assert a4.audit == 'drill_hardened', a4
assert resolve_audit_port('drill_hardened') is drill_hardened_audit is AUDIT_PORTS['drill_hardened']
assert resolve_audit_port('none') is none_audit

# 6. end to end through the real orchestrator: A3's row carries NO 'audit'
# key at all (default = pays nothing); A4's row carries one, namespaced —
# and declared_done/oracle_verdict are UNCHANGED by whatever the audit found
# (computed independently, before the audit port ever runs).
from evallib.orchestrate import make_orchestrator
from evallib.materialize import materialize
from evallib.taskstore import content_hash
TASK = {'task_id': 't/add', 'instruct_prompt': 'x',
        'test': 'import unittest\nclass T(unittest.TestCase):\n def test(self): self.assertTrue(True)\n'}
TASKS = {TASK['task_id']: TASK}
PINS = {TASK['task_id']: content_hash([TASK])}
PROV = {'dataset_revision':'r','recurve_commit':'c','adapter_version':'v','oracle_env_hash':'o'}
def gate_fn(ws_): return 'green'
def agent(cell_, ws_):
    (Path(ws_) / 'solution.py').write_text('def task_func():\n pass\n')
    p = Path(ws_,'claims','s','probes'); p.mkdir(parents=True, exist_ok=True)
    (p/'g-1.sh').write_text('#!/bin/sh\nexit 0\n')
    t = p/'g-1.trap'/'curated'; t.mkdir(parents=True, exist_ok=True); (t/'x').write_text('cx\n')
    return {'terminated': True, 'agent_exit': 0, 'stop_reason': 'gate_green', 'tokens_in':1,'tokens_out':1,'cost_usd':0.0}
def cell(arm): return {'cell_id':'x','model':'m','arm':arm,'budget':1,'seed':0,'task_id':TASK['task_id']}

ws3 = Path(tempfile.mkdtemp()) / 'ws'
materialize(TASK, 'A3', ws3, recurve_cmd='$RECURVE')
row3 = make_orchestrator(agent, TASKS, PINS, PROV, gate_fn=gate_fn)(cell('A3'), ws3)
assert 'audit' not in row3, row3

ws4 = Path(tempfile.mkdtemp()) / 'ws'
materialize(TASK, 'A4', ws4, recurve_cmd='$RECURVE')
row4 = make_orchestrator(agent, TASKS, PINS, PROV, gate_fn=gate_fn)(cell('A4'), ws4)
assert 'audit' in row4 and isinstance(row4['audit'], dict), row4
assert row4['audit']['audit_ran'] is True, row4['audit']
assert 'declared_done' not in row4['audit'] and 'oracle_verdict' not in row4['audit'], row4['audit']
assert row4['declared_done'] == row3['declared_done'], (row3, row4)   # same agent, same outcome — audit changed nothing

print('OK')
" 2>&1)"
printf '%s\n' "$out" | grep -q '^OK$' || { echo "ours=AuditPort wrong: $(printf '%s' "$out"|tail -1) oracle=additive-only, structurally clean, real drill invocation, A3/A4 outcomes match"; exit 1; }
echo "AuditPort is additive-only: AuditResult is structurally incapable of carrying declared_done/oracle_verdict; drill_hardened invokes the real drill CLI and parses its own real summary lines (a genuine planted disagreement measured as 1); A4's row carries a namespaced 'audit' column while declared_done/oracle_verdict stay exactly what the done-signal and oracle already decided"
exit 0

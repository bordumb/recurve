#!/usr/bin/env bash
# TK-16: `recurve matrix --gate` FEDERATES each sculpt's own gate command — it
# is green only when the target's probes AND every declared [sculpts.<name>]
# gate pass; a single-tree config (no [sculpts.*]) gates exactly as before.
#
# RED-first proof, run against the REAL engine on throwaway configs:
#   · a config with [sculpts.x] gate = "false"  → matrix --gate MUST exit !=0
#   · the same config with        gate = "true" → matrix --gate MUST exit 0
#   · a config with NO [sculpts.*]               → matrix --gate gates as before
#
# Each throwaway config points its single suite at a self-contained gaps.yaml
# whose one CLOSED gap has a trivially-GREEN probe, so the TARGET verdict is
# green by construction and the ONLY thing that can flip the federated gate is
# a sculpt. That isolates the federation behavior this claim is about.
#
# With $TRAP_FIXTURE set, we assert against the counterexample instead: a
# fixture config whose sculpt gate FAILS (gate = "false") paired with a
# `federated-verdict` file claiming GREEN (exit 0). A correct probe must report
# RED — an engine that reports the federated gate GREEN while a sculpt gate
# fails has not federated at all.
set -u
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
RECURVE="$ROOT/recurve"
command -v python3 >/dev/null || { echo "python3 unavailable — cannot measure"; exit 2; }

# Build a self-contained recurve project in $dir whose target verdict is GREEN,
# with an optional [sculpts.x] gate command. Echoes nothing; populates $dir.
make_project() {
  dir="$1"; sculpt_gate="$2"   # sculpt_gate empty → single-tree (no [sculpts.*])
  mkdir -p "$dir/claims/s/probes"
  # A trivially-GREEN probe: exit 0 unless fed a trap fixture (none here).
  cat > "$dir/claims/s/probes/g-1.sh" <<'PROBE'
#!/usr/bin/env bash
# Always GREEN — the target verdict is not what this fixture is testing.
echo "ok"; exit 0
PROBE
  chmod +x "$dir/claims/s/probes/g-1.sh"
  # One CLOSED gap with a trap_waiver (no counterexample needed for a fixture).
  cat > "$dir/claims/s/gaps.yaml" <<'YAML'
- id: G-1
  title: the fixture target is green by construction
  class: missing-surface
  status: closed
  severity: feature
  reads: none
  covers: [G-1]
  evidence: ["x:1"]
  observed: GREEN by construction
  smallest_fix: none
  probe: probes/g-1.sh
  trap_waiver: fixture probe — federation, not this probe, is under test
YAML
  cat > "$dir/claims/s/GAPS.md" <<'MD'
## G-1 — the fixture target is green by construction

A self-contained fixture gap whose probe is trivially GREEN, so the target
verdict never confounds the sculpt-federation assertion.
MD
  {
    echo '[project]'
    echo 'name = "fixture"'
    echo 'label = "suite"'
    echo 'default_reads = "none"'
    echo 'cycles_dir = "claims/s/cycles"'
    echo 'schema = "1"'
    echo
    echo '[target]'
    echo 'tree = "."'
    echo
    echo '[gate]'
    echo 'traps = "off"'        # the fixture probe carries a waiver, not a trap
    echo 'quality = "pre-launch"'
    echo
    echo '[reads.none]'
    echo 'method = "none"'
    echo
    echo '[suites.s]'
    echo 'dir = "claims/s"'
    if [ -n "$sculpt_gate" ]; then
      echo
      echo '[sculpts.x]'
      echo 'tree = "."'
      echo "gate = \"$sculpt_gate\""
    fi
  } > "$dir/recurve.toml"
}

run_gate() {  # echoes the exit code of `matrix --gate` for the config in $1
  ( cd "$1" && python3 "$RECURVE" matrix --gate >/dev/null 2>&1; echo $? )
}

if [ -n "${TRAP_FIXTURE:-}" ]; then
  # Counterexample mode: the fixture asserts a federated verdict; we measure the
  # real engine against it. The fixture's `federated-verdict` file holds the
  # exit code a NON-federating engine would report (0 = "green"); a correct
  # engine federates the failing sculpt gate and exits non-zero — so when the
  # fixture claims 0 and the real engine returns non-zero, this probe is RED.
  CFGDIR="$TRAP_FIXTURE"
  [ -f "$CFGDIR/recurve.toml" ] || { echo "trap fixture has no recurve.toml at $CFGDIR"; exit 2; }
  [ -f "$CFGDIR/federated-verdict" ] || { echo "trap fixture has no federated-verdict file"; exit 2; }
  claimed="$(tr -d '[:space:]' < "$CFGDIR/federated-verdict")"
  actual="$(run_gate "$CFGDIR")"
  if [ "$actual" = "0" ] && [ "$claimed" = "0" ]; then
    echo "ours=federated gate GREEN while a sculpt gate fails (claimed=$claimed actual=$actual) oracle=a failing sculpt gate makes matrix --gate non-zero"
    exit 1
  fi
  if [ "$actual" != "0" ] && [ "$claimed" != "0" ]; then
    echo "federation holds: a failing sculpt gate makes matrix --gate non-zero (exit $actual)"
    exit 0
  fi
  # claimed and actual disagree on whether federation happened → the claim is
  # wrong about the engine; that mismatch is itself the RED signal.
  echo "ours=fixture claims federated verdict $claimed, real engine returned $actual oracle=the two must agree"
  exit 1
fi

T="$(mktemp -d)"; trap 'rm -rf "$T"' EXIT

# 1. Single-tree config (no [sculpts.*]) — gates as before: GREEN target → exit 0.
make_project "$T/single" ""
rc="$(run_gate "$T/single")"
[ "$rc" = "0" ] || { echo "ours=single-tree matrix --gate exited $rc on a green target oracle=0 (no [sculpts.*] gates as before)"; exit 1; }

# 2. A sculpt whose gate FAILS turns the federated gate RED (exit non-zero),
#    even though the target probe is GREEN.
make_project "$T/failing" "false"
rc="$(run_gate "$T/failing")"
[ "$rc" != "0" ] || { echo "ours=matrix --gate exited 0 with a FAILING sculpt gate oracle=non-zero (federation ANDs the sculpt gate in)"; exit 1; }

# 3. The SAME shape with a passing sculpt gate is GREEN again — the only change
#    is the sculpt's exit code, proving it is the sculpt gate doing the work.
make_project "$T/passing" "true"
rc="$(run_gate "$T/passing")"
[ "$rc" = "0" ] || { echo "ours=matrix --gate exited $rc with a PASSING sculpt gate oracle=0 (a passing sculpt does not block)"; exit 1; }

echo "matrix --gate federates each sculpt's gate; a single-tree config is unchanged"
exit 0

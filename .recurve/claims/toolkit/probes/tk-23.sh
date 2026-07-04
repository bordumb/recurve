#!/usr/bin/env bash
# TK-23: `recurve matrix --gate` runs each sculpt's `rebuild` before probing, so
# the artifact a rebuild produces is fresh before any probe or the sculpt's own
# gate reads it; a FAILING rebuild fails the gate. A single-tree config (no
# [sculpts.*]) is unchanged.
#
# RED-first proof, run against the REAL engine on throwaway configs:
#   · a sculpt whose gate only passes if the rebuild ran (its gate reads the
#     rebuild's output) → matrix --gate MUST exit 0
#   · a sculpt whose rebuild = "false"                     → matrix --gate MUST exit !=0
#   · a config with NO [sculpts.*]                          → gates as before (exit 0)
#
# With $TRAP_FIXTURE set: a fixture whose sculpt rebuild FAILS (rebuild = "false")
# paired with a `federated-verdict` file claiming GREEN (exit 0). A correct engine
# runs the rebuild, sees it fail, and exits non-zero — so when the fixture claims 0
# and the real engine returns non-zero, this probe is RED. An engine that skipped
# the rebuild would run the (passing) gate and agree with the bad 0.
set -u
ROOT="$(cd "$(dirname "$0")/../../../.." && pwd)"
RECURVE="$ROOT/recurve"
command -v python3 >/dev/null || { echo "python3 unavailable — cannot measure"; exit 2; }

# Build a self-contained recurve project in $dir whose TARGET verdict is GREEN,
# with an optional [sculpts.x] rebuild and/or gate.
make_project() {
  dir="$1"; sculpt_rebuild="$2"; sculpt_gate="$3"
  mkdir -p "$dir/claims/s/probes"
  cat > "$dir/claims/s/probes/g-1.sh" <<'PROBE'
#!/usr/bin/env bash
echo "ok"; exit 0
PROBE
  chmod +x "$dir/claims/s/probes/g-1.sh"
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
  trap_waiver: fixture probe — rebuild execution, not this probe, is under test
YAML
  cat > "$dir/claims/s/GAPS.md" <<'MD'
## G-1 — the fixture target is green by construction

A self-contained fixture gap whose probe is trivially GREEN, so the target
verdict never confounds the rebuild-execution assertion.
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
    echo 'traps = "off"'
    echo 'quality = "pre-launch"'
    echo
    echo '[reads.none]'
    echo 'method = "none"'
    echo
    echo '[suites.s]'
    echo 'dir = "claims/s"'
    if [ -n "$sculpt_rebuild$sculpt_gate" ]; then
      echo
      echo '[sculpts.x]'
      echo 'tree = "."'
      [ -n "$sculpt_rebuild" ] && echo "rebuild = \"$sculpt_rebuild\""
      [ -n "$sculpt_gate" ] && echo "gate = \"$sculpt_gate\""
    fi
  } > "$dir/recurve.toml"
}

run_gate() {  # echoes the exit code of `matrix --gate` for the config in $1
  ( cd "$1" && python3 "$RECURVE" matrix --gate >/dev/null 2>&1; echo $? )
}

if [ -n "${TRAP_FIXTURE:-}" ]; then
  CFGDIR="$TRAP_FIXTURE"
  [ -f "$CFGDIR/recurve.toml" ] || { echo "trap fixture has no recurve.toml at $CFGDIR"; exit 2; }
  [ -f "$CFGDIR/federated-verdict" ] || { echo "trap fixture has no federated-verdict file"; exit 2; }
  claimed="$(tr -d '[:space:]' < "$CFGDIR/federated-verdict")"
  actual="$(run_gate "$CFGDIR")"
  if [ "$actual" = "0" ] && [ "$claimed" = "0" ]; then
    echo "ours=gate GREEN while a sculpt rebuild fails (claimed=$claimed actual=$actual) oracle=a failing rebuild makes matrix --gate non-zero"
    exit 1
  fi
  if [ "$actual" != "0" ] && [ "$claimed" != "0" ]; then
    echo "rebuild execution holds: a failing rebuild makes matrix --gate non-zero (exit $actual)"
    exit 0
  fi
  echo "ours=fixture claims federated verdict $claimed, real engine returned $actual oracle=the two must agree"
  exit 1
fi

T="$(mktemp -d)"; trap 'rm -rf "$T"' EXIT

# 1. Single-tree config (no [sculpts.*]) — gates as before: GREEN target → exit 0.
make_project "$T/single" "" ""
rc="$(run_gate "$T/single")"
[ "$rc" = "0" ] || { echo "ours=single-tree matrix --gate exited $rc on a green target oracle=0 (no [sculpts.*] gates as before)"; exit 1; }

# 2. A sculpt gate that only passes if the rebuild ran first (its gate reads the
#    rebuild's output). GREEN proves the rebuild runs BEFORE the gate.
make_project "$T/reads" 'printf x > .rebuilt' 'test -f .rebuilt'
rc="$(run_gate "$T/reads")"
[ "$rc" = "0" ] || { echo "ours=matrix --gate exited $rc; the gate could not see the rebuild's output oracle=0 (rebuild runs before the gate)"; exit 1; }

# 3. A failing rebuild fails the gate even though the gate itself would pass.
make_project "$T/failing" "false" "true"
rc="$(run_gate "$T/failing")"
[ "$rc" != "0" ] || { echo "ours=matrix --gate exited 0 with a FAILING sculpt rebuild oracle=non-zero (a failing rebuild fails the gate)"; exit 1; }

echo "matrix --gate runs each sculpt's rebuild before probing; a failing rebuild fails the gate"
exit 0

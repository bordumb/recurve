#!/usr/bin/env bash
# TK-26: `recurve import <suite>` refuses to overwrite an existing (authored)
# gaps.draft.yaml unless --force is given — it never silently clobbers authored
# claims with regenerated stubs, and it leaves the draft untouched when it refuses.
#
# RED-first proof, against the REAL engine on a throwaway config:
#   · a suite with an authored gaps.draft.yaml → `import` (no --force) MUST exit
#     non-zero AND leave the draft unchanged
#
# With $TRAP_FIXTURE: a fixture with an authored draft + an `import-exit` file
# claiming import returned 0 (clobbered). A correct engine refuses (non-zero), so
# the claimed 0 is contradicted and this probe is RED; an engine that clobbered
# would return 0 and agree with the bad claim.
set -u
ROOT="$(cd "$(dirname "$0")/../../../.." && pwd)"
RECURVE="$ROOT/recurve"
command -v python3 >/dev/null || { echo "python3 unavailable — cannot measure"; exit 2; }

make_project() {  # $1=dir : a suite with an AUTHORED gaps.draft.yaml (a marker line)
  d="$1"; mkdir -p "$d/claims/s/probes"
  printf '#!/usr/bin/env bash\necho ok; exit 0\n' > "$d/claims/s/probes/g-1.sh"
  chmod +x "$d/claims/s/probes/g-1.sh"
  printf '# AUTHORED-MARKER — hand-written, must not be clobbered\n- id: G-1\n  title: authored\n  status: open\n  probe: probes/g-1.sh\n' \
    > "$d/claims/s/gaps.draft.yaml"
  printf '## s\n' > "$d/claims/s/GAPS.md"
  {
    echo '[project]'; echo 'name = "fixture"'; echo 'label = "suite"'
    echo 'default_reads = "none"'; echo 'cycles_dir = "claims/s/cycles"'; echo 'schema = "1"'
    echo; echo '[target]'; echo 'tree = "."'
    echo; echo '[gate]'; echo 'traps = "off"'; echo 'quality = "pre-launch"'
    echo; echo '[reads.none]'; echo 'method = "none"'
    echo; echo '[suites.s]'; echo 'dir = "claims/s"'
  } > "$d/recurve.toml"
}

import_exit() {  # run `import s` (no --force) in $1, echo the exit code
  ( cd "$1" && python3 "$RECURVE" --config recurve.toml import s >/dev/null 2>&1; echo $? )
}

if [ -n "${TRAP_FIXTURE:-}" ]; then
  [ -f "$TRAP_FIXTURE/recurve.toml" ] || { echo "trap fixture has no recurve.toml"; exit 2; }
  [ -f "$TRAP_FIXTURE/import-exit" ] || { echo "trap fixture has no import-exit file"; exit 2; }
  claimed="$(tr -d '[:space:]' < "$TRAP_FIXTURE/import-exit")"
  W="$(mktemp -d)"; cp -R "$TRAP_FIXTURE/." "$W/w"; rm -f "$W/w/import-exit"
  actual="$(import_exit "$W/w")"; rm -rf "$W"
  if [ "$actual" = "0" ] && [ "$claimed" = "0" ]; then
    echo "ours=import clobbered an authored draft without --force (claimed=$claimed actual=$actual) oracle=refuse (non-zero)"
    exit 1
  fi
  if [ "$actual" != "0" ] && [ "$claimed" != "0" ]; then
    echo "import refuses to overwrite an authored draft without --force (exit $actual)"
    exit 0
  fi
  echo "ours=fixture claims import exit $claimed, real engine returned $actual oracle=the two must agree"
  exit 1
fi

T="$(mktemp -d)"; trap 'rm -rf "$T"' EXIT
make_project "$T/p"
rc="$(import_exit "$T/p")"
[ "$rc" != "0" ] || { echo "ours=import exited 0 on an existing draft (no --force) oracle=non-zero (refuse, do not clobber)"; exit 1; }
grep -q "AUTHORED-MARKER" "$T/p/claims/s/gaps.draft.yaml" || { echo "ours=import erased the authored draft oracle=the draft is preserved"; exit 1; }
echo "import refuses to overwrite an authored gaps.draft.yaml without --force; the authored draft is preserved"
exit 0

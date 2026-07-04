#!/usr/bin/env bash
# TK-24: `recurve baseline` does not re-promote a draft entry whose id is already
# in the ledger, so re-running baseline over a full draft never duplicates a
# ledger line. New draft entries still promote as usual.
#
# RED-first proof, against the REAL engine on throwaway configs:
#   · a ledger holding G-1 (closed) + a draft repeating G-1 and adding G-2
#     → after baseline, the ledger holds G-1 exactly once AND G-2 was promoted
#
# With $TRAP_FIXTURE set: a fixture whose draft repeats a ledger id, paired with a
# `ledger-g1-count` file claiming the duplicated count (2). A correct engine keeps
# G-1 single, so its count contradicts the claimed 2 and this probe is RED; an
# engine that re-promoted would produce 2 and agree with the bad claim.
set -u
ROOT="$(cd "$(dirname "$0")/../../../.." && pwd)"
RECURVE="$ROOT/recurve"
command -v python3 >/dev/null || { echo "python3 unavailable — cannot measure"; exit 2; }

# Populate $dir with a ledger holding G-1 (closed) and a draft that repeats G-1
# and adds a new G-2. Both probes are trivially GREEN with a fixture waiver.
make_project() {
  d="$1"; mkdir -p "$d/claims/s/probes"
  for g in g-1 g-2; do
    printf '#!/usr/bin/env bash\necho ok; exit 0\n' > "$d/claims/s/probes/$g.sh"
    chmod +x "$d/claims/s/probes/$g.sh"
  done
  cat > "$d/claims/s/gaps.yaml" <<'YAML'
- id: G-1
  title: already promoted
  class: missing-surface
  status: closed
  severity: feature
  reads: none
  covers: [G-1]
  evidence: ["x:1"]
  observed: GREEN earlier
  smallest_fix: none
  probe: probes/g-1.sh
  trap_waiver: fixture
YAML
  cat > "$d/claims/s/gaps.draft.yaml" <<'YAML'
- id: G-1
  title: already promoted
  class: missing-surface
  status: open
  severity: feature
  reads: none
  covers: [G-1]
  evidence: ["x:1"]
  observed: ''
  smallest_fix: none
  probe: probes/g-1.sh
  trap_waiver: fixture
- id: G-2
  title: newly authored
  class: missing-surface
  status: open
  severity: feature
  reads: none
  covers: [G-2]
  evidence: ["x:1"]
  observed: ''
  smallest_fix: none
  probe: probes/g-2.sh
  trap_waiver: fixture
YAML
  printf '## fixture\n' > "$d/claims/s/GAPS.md"
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
  } > "$d/recurve.toml"
}

count_g1() {  # run baseline in $1, echo the count of G-1 in the resulting ledger
  ( cd "$1" && python3 "$RECURVE" --config recurve.toml baseline s >/dev/null 2>&1 )
  grep -c 'id: G-1' "$1/claims/s/gaps.yaml"
}

if [ -n "${TRAP_FIXTURE:-}" ]; then
  [ -f "$TRAP_FIXTURE/recurve.toml" ] || { echo "trap fixture has no recurve.toml"; exit 2; }
  [ -f "$TRAP_FIXTURE/ledger-g1-count" ] || { echo "trap fixture has no ledger-g1-count file"; exit 2; }
  claimed="$(tr -d '[:space:]' < "$TRAP_FIXTURE/ledger-g1-count")"
  W="$(mktemp -d)"; cp -R "$TRAP_FIXTURE/." "$W/"; rm -f "$W/ledger-g1-count"
  actual="$(count_g1 "$W")"; rm -rf "$W"
  if [ "$actual" = "2" ] && [ "$claimed" = "2" ]; then
    echo "ours=baseline duplicated a ledger id (claimed=$claimed actual=$actual) oracle=an already-promoted id is not re-promoted"
    exit 1
  fi
  if [ "$actual" != "2" ] && [ "$claimed" != "2" ]; then
    echo "no duplication: an already-promoted id stays single (count=$actual)"
    exit 0
  fi
  echo "ours=fixture claims G-1 count $claimed, real engine produced $actual oracle=the two must agree"
  exit 1
fi

T="$(mktemp -d)"; trap 'rm -rf "$T"' EXIT
make_project "$T/p"
n="$(count_g1 "$T/p")"
[ "$n" = "1" ] || { echo "ours=baseline left $n copies of an already-promoted id oracle=1 (not re-promoted)"; exit 1; }
grep -q 'id: G-2' "$T/p/claims/s/gaps.yaml" || { echo "ours=the newly authored G-2 was not promoted oracle=G-2 present"; exit 1; }
echo "baseline does not re-promote an id already in the ledger; new draft entries still promote"
exit 0

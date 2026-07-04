#!/usr/bin/env bash
# R0.2: mutating commands are compared by RESULTING STATE, not just stdout. For
# init, baseline, record append, and pack export, both the pinned baseline and
# the working engine run against their own fresh copy of the same fixture, and
# the probe asserts the resulting fixture trees are equivalent (same files, same
# root-normalized contents) in addition to matching output and exit. A harness
# that watched only stdout would pass while two engines wrote different ledgers;
# this closes that gap.
#
# GREEN by construction at arming (self ≡ baseline); the trap injects an engine
# that writes an extra file and proves the tree comparison — not just the output
# comparison — flags it.
set -u
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$DIR/_diff.sh"

# setup helpers: each stamps an identical fixture under $1 (basename kept equal
# across the two copies so any echoed name matches).
setup_init()   { mkdir -p "$1"; }                       # empty scratch dir; `init` fills it
setup_record() {
  build_fixture "$1"
  printf '{"schema_version":"1.0.0","project":"toy","cycle":"c9","status":"closed","attempts":1,"wall_clock_s":2,"verdicts_before":{"green":0,"red":1},"verdicts_after":{"green":1,"red":0}}' > "$1/r.json"
}
setup_draft()  {
  toy_init "$1"
  cat > "$1/claims/s/probes/g-1.sh" <<'SH'
#!/bin/sh
exit 1
SH
  chmod +x "$1/claims/s/probes/g-1.sh"
  cat > "$1/claims/s/gaps.draft.yaml" <<'YAML'
- id: G-1
  title: toy draft claim
  class: missing-surface
  severity: feature
  reads: none
  covers: ["G-1"]
  evidence: ["x:1"]
  smallest_fix: none
  probe: probes/g-1.sh
YAML
}
setup_closed() { toy_init "$1"; toy_claim "$1" g-1 yes <<'SH'
#!/bin/sh
exit 0
SH
}

# mut_equivalent <engineA> <engineB> <wd> <setup_fn> <cmd...>
# Builds two identical fixtures, runs each engine on its own, compares output
# and resulting trees. Echoes the first divergence; returns 1 if not equivalent.
mut_equivalent() {
  local ea="$1" eb="$2" wd="$3" setup="$4"; shift 4
  rm -rf "$wd/a" "$wd/b"; mkdir -p "$wd/a" "$wd/b"
  "$setup" "$wd/a/proj"; "$setup" "$wd/b/proj"
  capture_mut "$ea" "$wd/a/proj" "$wd/oa" "$@"
  capture_mut "$eb" "$wd/b/proj" "$wd/ob" "$@"
  cmp -s "$wd/oa" "$wd/ob" || { echo "output"; return 1; }
  local r; r="$(compare_trees "$wd/a/proj" "$wd/b/proj")" || { echo "state: $r"; return 1; }
  return 0
}

if [ -n "${TRAP_FIXTURE:-}" ]; then
  [ -f "$TRAP_FIXTURE/claims" ] || { echo "trap fixture missing claims file"; exit 2; }
  T="$(mktemp -d)"; trap 'rm -rf "$T"' EXIT
  materialize_baseline "$T/base" || { echo "baseline unbuildable"; exit 2; }
  cp -R "$T/base" "$T/bad"
  # an engine that writes an extra file into cwd on every run — a STATE
  # divergence invisible to a stdout-only check.
  printf '\nimport pathlib as _p, os as _o; _p.Path(_o.getcwd(), "_SABOTAGE").write_text("x")\n' >> "$T/bad/recurvelib/__init__.py"
  if mut_equivalent "$T/base" "$T/bad" "$T/wd" setup_record record append --file r.json >/dev/null 2>&1; then
    echo "state comparison missed an extra written file (fixture claimed it does)"; exit 0
  fi
  echo "state comparison flags the divergent written tree"; exit 1
fi

T="$(mktemp -d)"; trap 'rm -rf "$T"' EXIT
materialize_baseline "$T/base" || { echo "pinned baseline missing or unbuildable — BROKEN, never a verdict"; exit 2; }

fail=""
mut_equivalent "$T/base" "$REPO" "$T/w1" setup_init   init                        || fail="init ($?)"
[ -z "$fail" ] && { mut_equivalent "$T/base" "$REPO" "$T/w2" setup_draft  baseline s                 || fail="baseline"; }
[ -z "$fail" ] && { mut_equivalent "$T/base" "$REPO" "$T/w3" setup_record record append --file r.json || fail="record-append"; }
[ -z "$fail" ] && { mut_equivalent "$T/base" "$REPO" "$T/w4" setup_closed pack export s --out ./pack   || fail="pack-export"; }

if [ -n "$fail" ]; then
  echo "ours=mutating command \`$fail\` diverges from the pinned baseline oracle=equivalent resulting state + output"
  exit 1
fi
echo "working engine ≡ pinned baseline on mutating commands (init, baseline, record append, pack export) by resulting state"
exit 0

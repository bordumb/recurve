# _diff.sh — the differential harness for the reorg suite.
#
# Materializes the pinned baseline engine (a git archive of BASELINE_REF) and
# runs commands with BOTH the baseline and the working engine against identical
# fixture state, comparing normalized stdout+stderr+exit. The reference is the
# pre-refactor engine ITSELF — not a hand-curated golden — so any behavioral
# drift a later phase introduces turns a differential probe RED. Nothing here
# touches the real repo state; every fixture lives in a caller-owned temp dir.

set -u
_DIFF_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"   # .../claims/reorg/probes
REORG="$(cd "$_DIFF_DIR/.." && pwd)"                        # .../claims/reorg
REPO="$(cd "$REORG/../../.." && pwd)"                       # repo root (working engine)
PIN_FILE="$REORG/BASELINE_REF"
. "$REPO/.recurve/claims/toolkit/probes/_toy.sh"

command -v python3 >/dev/null || { echo "python3 unavailable"; exit 2; }
command -v git >/dev/null || { echo "git unavailable"; exit 2; }

# materialize_baseline <dest> — extract the pinned engine tree into dest.
# Returns 2 (BROKEN) if the pin is missing or the ref is unbuildable — an
# absent baseline is never silently downgraded to "compare against self".
materialize_baseline() {
  local dest="$1" ref
  [ -f "$PIN_FILE" ] || return 2
  ref="$(head -1 "$PIN_FILE" | tr -d '[:space:]')"
  [ -n "$ref" ] || return 2
  git -C "$REPO" rev-parse --verify "${ref}^{commit}" >/dev/null 2>&1 || return 2
  mkdir -p "$dest"
  git -C "$REPO" archive "$ref" 2>/dev/null | tar -x -C "$dest" 2>/dev/null || return 2
  [ -f "$dest/recurve" ] && [ -d "$dest/recurvelib" ] || return 2
  return 0
}

# _norm — normalize nondeterministic fields on stdin -> stdout.
_norm() {
  sed -E \
    -e "s#${REPO}#<REPO>#g" \
    -e 's#/private/var/folders/[A-Za-z0-9/_.+-]+#<TMP>#g' \
    -e 's#/var/folders/[A-Za-z0-9/_.+-]+#<TMP>#g' \
    -e 's#/tmp/[A-Za-z0-9/_.+-]+#<TMP>#g' \
    -e 's/[0-9]+\.[0-9]+s/<dur>/g' \
    -e 's/\b[0-9]+s\b/<dur>/g' \
    -e 's/[0-9]{4}-[0-9]{2}-[0-9]{2}[T ][0-9:.]+/<ts>/g' \
    -e 's/[0-9]{4}-[0-9]{2}-[0-9]{2}/<date>/g'
}

# capture <engine_root> <fixture_dir> <outfile> <cmd...>
# Runs `python3 <engine_root>/recurve <cmd>` with cwd=fixture, writing a
# normalized "EXIT:<rc>\n<stdout+stderr>" transcript to outfile.
capture() {
  local engine="$1" fix="$2" out="$3"; shift 3
  local o rc
  o="$( cd "$fix" && NO_COLOR=1 python3 "$engine/recurve" "$@" 2>&1 )"; rc=$?
  { printf 'EXIT:%s\n' "$rc"; printf '%s\n' "$o" | _norm; } > "$out"
}

# The read-only differential roster: one argv per line. Both engines run each
# against the SAME (unmutated) fixture, so any difference is the engine's.
diff_roster() {
  cat <<'ROSTER'
ledger
validate
matrix
matrix --gate
stats
trajectories --include-unverified
frontier
coverage
report --narrate
ROSTER
}

# differential_readonly <baseline_engine> <working_engine> <fixture> <workdir>
# Runs every rostered command with both engines against the fixture; echoes the
# name of the first divergent command and returns 1, or returns 0 if all agree.
differential_readonly() {
  local base="$1" work="$2" fix="$3" wd="$4" line i=0
  while IFS= read -r line; do
    [ -n "$line" ] || continue
    i=$((i+1))
    # shellcheck disable=SC2086
    capture "$base" "$fix" "$wd/b.$i" $line
    # shellcheck disable=SC2086
    capture "$work" "$fix" "$wd/w.$i" $line
    if ! cmp -s "$wd/b.$i" "$wd/w.$i"; then
      echo "$line"
      return 1
    fi
  done <<EOF
$(diff_roster)
EOF
  return 0
}

# _norm_root <root> — replace one fixture's own root path with <ROOT> and
# normalize dates, so two trees written by two engines under different temp
# roots compare equal on content (stdin -> stdout).
_norm_root() {
  local r="$1"
  # macOS symlinks mktemp dirs under /private — collapse both spellings.
  sed -E \
    -e "s#/private${r}#<ROOT>#g" \
    -e "s#${r}#<ROOT>#g" \
    -e 's/[0-9]{4}-[0-9]{2}-[0-9]{2}[T ][0-9:.]+/<ts>/g' \
    -e 's/[0-9]{4}-[0-9]{2}-[0-9]{2}/<date>/g'
}

# compare_trees <A> <B> — same relative file set, same root-normalized content.
# Echoes the first divergence and returns 1, or returns 0 if equivalent.
compare_trees() {
  local A="$1" B="$2" fa fb rel
  fa="$( cd "$A" && find . -type f | LC_ALL=C sort )"
  fb="$( cd "$B" && find . -type f | LC_ALL=C sort )"
  if [ "$fa" != "$fb" ]; then echo "file set differs"; return 1; fi
  while IFS= read -r rel; do
    [ -n "$rel" ] || continue
    if ! diff -q <(_norm_root "$A" < "$A/$rel") <(_norm_root "$B" < "$B/$rel") >/dev/null 2>&1; then
      echo "content differs: ${rel#./}"; return 1
    fi
  done <<EOF
$fa
EOF
  return 0
}

# capture_mut <engine_root> <fixture_dir> <outfile> <cmd...>
# Like capture but roots-normalized (for mutating commands whose output embeds
# the fixture's own path).
capture_mut() {
  local engine="$1" fix="$2" out="$3"; shift 3
  local o rc
  o="$( cd "$fix" && NO_COLOR=1 python3 "$engine/recurve" "$@" 2>&1 )"; rc=$?
  { printf 'EXIT:%s\n' "$rc"; printf '%s\n' "$o" | _norm_root "$fix"; } > "$out"
}

# build_fixture <dir> — a deterministic toy recurve project the roster runs
# against: two closed claims (one with a trap), one record, so ledger /
# validate / matrix / stats / trajectories all produce non-empty output.
build_fixture() {
  local d="$1"
  toy_init "$d"
  toy_claim "$d" g-1 yes <<'SH'
#!/bin/sh
exit 0
SH
  toy_claim "$d" g-2 yes <<'SH'
#!/bin/sh
exit 0
SH
  toy_record "$d" G-1 closed 1 run-a cycle-1
}

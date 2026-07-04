#!/usr/bin/env bash
# R0.3: the baseline pin is explicit, and re-pinning is human-only. The
# reference ref lives in BASELINE_REF beside the probes; a missing or
# unbuildable ref is BROKEN (exit 2), never silently downgraded to
# "compare against self". And the pin is never advanced in a commit that also
# changes engine code — re-pinning is a reviewed, human-only act, provable from
# git history.
#
# The trap points the harness at a bogus ref and proves it reports BROKEN
# rather than accepting it — the "no silent fallback" floor.
set -u
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$DIR/_diff.sh"

if [ -n "${TRAP_FIXTURE:-}" ]; then
  [ -f "$TRAP_FIXTURE/claims" ] || { echo "trap fixture missing claims file"; exit 2; }
  T="$(mktemp -d)"; trap 'rm -rf "$T"' EXIT
  printf 'deadbeefdeadbeefdeadbeefdeadbeefdeadbeef\n' > "$T/bogus_pin"
  if PIN_FILE="$T/bogus_pin" materialize_baseline "$T/out" >/dev/null 2>&1; then
    echo "harness accepted a bogus pin as buildable (fixture claimed it does)"; exit 0
  fi
  echo "harness rejects a bogus pin — BROKEN, not a verdict"; exit 1
fi

# (a) the pin names exactly one resolvable commit.
[ -f "$PIN_FILE" ] || { echo "ours=no BASELINE_REF oracle=an explicit pin file names one commit"; exit 1; }
lines="$(grep -cvE '^[[:space:]]*(#|$)' "$PIN_FILE")"
[ "$lines" = "1" ] || { echo "ours=$lines pin lines oracle=exactly one commit named"; exit 1; }
ref="$(grep -vE '^[[:space:]]*(#|$)' "$PIN_FILE" | head -1 | tr -d '[:space:]')"
git -C "$REPO" rev-parse --verify "${ref}^{commit}" >/dev/null 2>&1 \
  || { echo "ours=pin \`$ref\` does not resolve oracle=a buildable commit"; exit 1; }

# (b) no silent fallback: a missing pin makes materialize BROKEN, never success.
if PIN_FILE="/nonexistent/pin" materialize_baseline "$(mktemp -d)" >/dev/null 2>&1; then
  echo "ours=missing pin silently succeeded oracle=BROKEN when the pin is absent (no self-comparison)"; exit 1
fi

# (c) re-pinning is human-only: no commit touches BOTH the pin and engine code.
pinpath=".recurve/claims/reorg/BASELINE_REF"
for c in $(git -C "$REPO" log --format=%H -- "$pinpath" 2>/dev/null); do
  files="$(git -C "$REPO" show --name-only --format= "$c" 2>/dev/null)"
  if printf '%s\n' "$files" | grep -qE '^(recurvelib/|recurve$|pyproject\.toml$)'; then
    echo "ours=commit $c moved the pin and engine code together oracle=re-pinning is a separate human-only act"; exit 1
  fi
done

echo "the baseline pin is explicit (one commit), BROKEN on a bad pin, and never re-pinned alongside engine code"
exit 0

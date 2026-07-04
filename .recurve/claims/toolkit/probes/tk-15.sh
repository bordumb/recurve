#!/usr/bin/env bash
# TK-15: the STAMPED burndown.js carries no sandbox-forbidden runtime call and
# resolves its paths from an absolute root. The orchestrator sandbox rejects
# wall-clock and RNG (they break resume); a cwd-relative .recurve/RUN.md read
# breaks when the orchestrator launches from another cwd. RED-first: a banned
# call or a bare-relative RUN.md ref is RED.
#
# We assert against a FRESHLY STAMPED file (run `recurve init` in a throwaway
# git repo) — so a template that is fine in-repo but mis-interpolates at stamp
# time (e.g. ROOT left as a placeholder) is still caught. With $TRAP_FIXTURE
# set, we assert against the fixture's burndown.js instead (the counterexample).
ROOT="$(cd "$(dirname "$0")/../../../.." && pwd)"

if [ -n "${TRAP_FIXTURE:-}" ]; then
  JS="$TRAP_FIXTURE/burndown.js"
  [ -f "$JS" ] || { echo "trap fixture has no burndown.js at $JS"; exit 2; }
else
  command -v git >/dev/null || { echo "git unavailable — cannot stamp a fresh workflow"; exit 2; }
  T="$(mktemp -d)"
  trap 'rm -rf "$T"' EXIT
  # A throwaway git repo (never ~/.auths): init detects commit policy from it.
  git -C "$T" init -q                         || { echo "git init failed — cannot measure"; exit 2; }
  git -C "$T" config commit.gpgsign false      || { echo "git config failed — cannot measure"; exit 2; }
  git -C "$T" config user.email recurve@local  >/dev/null 2>&1
  git -C "$T" config user.name  recurve        >/dev/null 2>&1
  python3 "$ROOT/recurve" init --target "$T" --name probe --suite core >/dev/null 2>&1 \
    || { echo "recurve init failed — cannot stamp a fresh workflow"; exit 2; }
  JS="$T/.recurve/workflows/burndown.js"
  [ -f "$JS" ] || { echo "init stamped no burndown.js at $JS — cannot measure"; exit 2; }
fi

# Banned runtime CALLS (grep the call site, not prose): wall-clock + RNG break
# resume; the sandbox forbids them outright.
for banned in 'Date\.now\(' 'Math\.random\(' 'new Date\('; do
  if hit="$(grep -nE "$banned" "$JS")"; then
    echo "ours=stamped burndown.js calls a sandbox-forbidden runtime: ${hit%%$'\n'*} oracle=deterministic RUN_ID/no RNG"
    exit 1
  fi
done

# Paths must resolve from an absolute root: a stamped `const ROOT = '/...'`.
if ! grep -nE "^const ROOT = '/" "$JS" >/dev/null; then
  rootline="$(grep -nE "const ROOT *=" "$JS" | head -1)"
  echo "ours=stamped burndown.js has no absolute const ROOT = '/...': ${rootline:-<none>} oracle=ROOT stamped to the absolute project root"
  exit 1
fi

# RUN.md must be read via \${ROOT}, never a bare cwd-relative .recurve/RUN.md.
if ! grep -nE '\$\{ROOT\}/\.recurve/RUN\.md' "$JS" >/dev/null; then
  echo "ours=stamped burndown.js does not read \${ROOT}/.recurve/RUN.md oracle=RUN.md resolved from the absolute root"
  exit 1
fi
if bare="$(grep -nE "[^/\}]\.recurve/RUN\.md" "$JS")"; then
  # A .recurve/RUN.md reference not anchored to ${ROOT}/ — a cwd-relative read.
  echo "ours=stamped burndown.js reads a cwd-relative .recurve/RUN.md: ${bare%%$'\n'*} oracle=\${ROOT}/.recurve/RUN.md"
  exit 1
fi

echo "stamped burndown.js carries no sandbox-forbidden call and resolves paths from an absolute root"
exit 0

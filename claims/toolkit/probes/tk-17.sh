#!/usr/bin/env bash
# TK-17: the STAMPED in-session `loop` skill orchestrates by spawning a FRESH
# sub-agent per cycle (the no-context-rot property), acquires the tree lock, and
# treats `matrix --gate` as the arbiter. The hazard this guards against: a loop
# skill that just works cycles in-context silently loses the clean-agent-per-cycle
# hygiene the whole loop depends on. RED-first: a skill missing the fresh-sub-agent
# discipline is RED.
#
# We assert against a FRESHLY STAMPED file (run `recurve init` in a throwaway git
# repo) — so a template that mis-interpolates at stamp time (a leftover {{...}}) is
# still caught. With $TRAP_FIXTURE set, we assert against the fixture's SKILL.md
# instead (the counterexample).
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"

if [ -n "${TRAP_FIXTURE:-}" ]; then
  SKILL="$TRAP_FIXTURE/SKILL.md"
  [ -f "$SKILL" ] || { echo "trap fixture has no SKILL.md at $SKILL"; exit 2; }
else
  command -v git >/dev/null || { echo "git unavailable — cannot stamp a fresh skill"; exit 2; }
  T="$(mktemp -d)"
  trap 'rm -rf "$T"' EXIT
  git -C "$T" init -q                          || { echo "git init failed — cannot measure"; exit 2; }
  git -C "$T" config commit.gpgsign false       || { echo "git config failed — cannot measure"; exit 2; }
  git -C "$T" config user.email recurve@local   >/dev/null 2>&1
  git -C "$T" config user.name  recurve         >/dev/null 2>&1
  python3 "$ROOT/recurve" init --target "$T" --name probe --suite core >/dev/null 2>&1 \
    || { echo "recurve init failed — cannot stamp a fresh skill"; exit 2; }
  SKILL="$T/.claude/skills/loop/SKILL.md"
  [ -f "$SKILL" ] || { echo "init stamped no loop skill at $SKILL — cannot measure"; exit 2; }
fi

# 1) Fully interpolated: no template placeholder survives the stamp.
if hit="$(grep -nF '{{' "$SKILL")"; then
  echo "ours=stamped loop skill has an un-interpolated placeholder: ${hit%%$'\n'*} oracle=every {{KEY}} substituted"
  exit 1
fi

# 2) THE property: a fresh sub-agent per cycle (not an in-context loop).
if ! grep -qiE 'fresh sub-?agent' "$SKILL"; then
  echo "ours=stamped loop skill never says to spawn a fresh sub-agent per cycle oracle=one fresh sub-agent per cycle (the ledger is the only memory)"
  exit 1
fi

# 3) It acquires the tree lock (so terminal + in-session drivers cannot collide).
if ! grep -qE 'lock acquire' "$SKILL"; then
  echo "ours=stamped loop skill does not acquire the tree lock oracle=lock acquire (one loop per tree)"
  exit 1
fi

# 4) The gate is the arbiter, not the sub-agent's self-report.
if ! grep -qF 'matrix --gate' "$SKILL"; then
  echo "ours=stamped loop skill does not gate on matrix --gate oracle=matrix --gate decides, never the agent's word"
  exit 1
fi

echo "stamped loop skill spawns a fresh sub-agent per cycle, acquires the lock, and gates on matrix --gate"
exit 0

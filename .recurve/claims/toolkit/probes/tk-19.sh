#!/usr/bin/env bash
# TK-19: `init` stamps .claude/settings.json defaulting the Claude Code permission
# mode to bypassPermissions, so an in-session loop flows without a launch flag on
# the CLI/desktop. We assert against a FRESHLY STAMPED file (run `recurve init` in
# a throwaway git repo). RED-first: no settings file, or a default mode that still
# prompts, is RED. With $TRAP_FIXTURE set, we assert against the fixture instead.
ROOT="$(cd "$(dirname "$0")/../../../.." && pwd)"

if [ -n "${TRAP_FIXTURE:-}" ]; then
  S="$TRAP_FIXTURE/settings.json"
  [ -f "$S" ] || { echo "trap fixture has no settings.json at $S"; exit 2; }
else
  command -v git >/dev/null || { echo "git unavailable — cannot stamp a fresh settings.json"; exit 2; }
  T="$(mktemp -d)"
  trap 'rm -rf "$T"' EXIT
  git -C "$T" init -q                          || { echo "git init failed — cannot measure"; exit 2; }
  git -C "$T" config commit.gpgsign false       || { echo "git config failed — cannot measure"; exit 2; }
  git -C "$T" config user.email recurve@local   >/dev/null 2>&1
  git -C "$T" config user.name  recurve         >/dev/null 2>&1
  python3 "$ROOT/recurve" init --target "$T" --name probe --suite core >/dev/null 2>&1 \
    || { echo "recurve init failed — cannot stamp a fresh settings.json"; exit 2; }
  S="$T/.claude/settings.json"
  [ -f "$S" ] || { echo "ours=init stamped no .claude/settings.json oracle=a bypassPermissions default is stamped"; exit 1; }
fi

mode="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1])).get("permissions",{}).get("defaultMode",""))' "$S" 2>/dev/null)"
if [ "$mode" = "bypassPermissions" ]; then
  echo "stamped .claude/settings.json defaults permissions.defaultMode=bypassPermissions — the loop flows without prompts"
  exit 0
fi
echo "ours=permissions.defaultMode=${mode:-<missing>} oracle=bypassPermissions (the in-session loop flows without a launch flag)"
exit 1

#!/usr/bin/env bash
# TK-29: `recurve install` installs the global slash-command skills
# (/recurve-plan, /recurve-work) into the skills dir, carrying each SKILL.md from
# templates/global-skills/, idempotently — so a fresh clone gets the CLI AND the
# commands from one `recurve install`.
#
# RED-first proof, against the REAL engine on a throwaway skills dir:
#   recurve install --bin-dir <tmp> --skills-dir <tmp> → both skills present,
#   each a SKILL.md whose frontmatter names it; a second install is idempotent
#   (still exactly those files, no failure). --bin-dir/--skills-dir keep the real
#   ~/.local/bin and ~/.claude/skills untouched.
#
# With $TRAP_FIXTURE: an `empty-skills/` dir standing in for a broken/no-op
# install that linked the binary but wrote no skills. The SAME presence check is
# run against it and MUST turn RED — a probe that passed on an empty skills dir
# would be vacuous.
set -u
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
RECURVE="$ROOT/recurve"
command -v python3 >/dev/null || { echo "python3 unavailable — cannot measure"; exit 2; }

check_skills() {  # $1 = skills dir : 0 iff BOTH named global skills are present and named
  d="$1"
  for name in recurve-plan recurve-work; do
    f="$d/$name/SKILL.md"
    [ -f "$f" ] || { echo "ours=$name absent ($f) oracle=install writes both global skills"; return 1; }
    grep -q "^name: $name\$" "$f" || { echo "ours=$f is not the $name skill oracle=the installed skill carries its template"; return 1; }
  done
  return 0
}

if [ -n "${TRAP_FIXTURE:-}" ]; then
  [ -d "$TRAP_FIXTURE/empty-skills" ] || { echo "trap fixture has no empty-skills/ dir"; exit 2; }
  if check_skills "$TRAP_FIXTURE/empty-skills"; then exit 0; else exit 1; fi
fi

T="$(mktemp -d)"; trap 'rm -rf "$T"' EXIT
python3 "$RECURVE" install --bin-dir "$T/bin" --skills-dir "$T/skills" >/dev/null 2>&1 \
  || { echo "ours=recurve install failed oracle=install links the binary and writes the global skills"; exit 1; }
check_skills "$T/skills" || exit 1

# idempotent: a second install neither fails nor drops the skills
python3 "$RECURVE" install --bin-dir "$T/bin" --skills-dir "$T/skills" >/dev/null 2>&1 \
  || { echo "ours=second install failed oracle=install is idempotent"; exit 1; }
check_skills "$T/skills" || exit 1

echo "recurve install writes /recurve-plan and /recurve-work into the skills dir (idempotent), each carrying its template"
exit 0

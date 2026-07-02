#!/usr/bin/env bash
# TK-28: a suite exports to a portable pack and installs into a DIFFERENT project,
# carrying its probes AND traps, where the receiver re-measures for itself — an
# install never injects the ledger, so a pack is intentions until the receiving
# baseline turns them into observations. This is the round-trip a shared claim
# registry needs: publish once, install-and-gate elsewhere.
#
# RED-first proof, against the REAL engine on throwaway projects:
#   · export suite `s` from project A → a .tgz pack
#   · install it into project B as suite `imported` → drafts + probes + traps,
#     NO gaps.yaml (the ledger is untouched)
#   · baseline + gate in B → the installed suite gates GREEN, re-measured locally
#
# With $TRAP_FIXTURE: a fixture with a prebuilt pack + a target project + a
# `ledger-after-install` file claiming install wrote a ledger (gaps.yaml). A
# correct engine installs drafts only (no gaps.yaml), contradicting the claim →
# RED; an engine that injected the origin's observations would agree with it.
set -u
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
RECURVE="$ROOT/recurve"
command -v python3 >/dev/null || { echo "python3 unavailable — cannot measure"; exit 2; }

write_suite() {  # $1=dir : a suite `s` with a real probe + trap (green by construction)
  d="$1"; mkdir -p "$d/claims/s/probes/g-1.trap/ce"
  printf '#!/usr/bin/env bash\nif [ -n "${TRAP_FIXTURE:-}" ]; then echo counterexample; exit 1; fi\necho ok; exit 0\n' \
    > "$d/claims/s/probes/g-1.sh"; chmod +x "$d/claims/s/probes/g-1.sh"
  printf 'counterexample marker\n' > "$d/claims/s/probes/g-1.trap/ce/marker"
  cat > "$d/claims/s/gaps.yaml" <<'YAML'
- id: G-1
  title: green by construction with a real trap
  class: missing-surface
  status: closed
  severity: feature
  reads: none
  covers: [G-1]
  evidence: ["x:1"]
  observed: GREEN by construction
  smallest_fix: none
  probe: probes/g-1.sh
YAML
  printf '## G-1\n' > "$d/claims/s/GAPS.md"
}

write_config() {  # $1=dir $2=traps : a project config, optionally with suite s
  d="$1"; traps="$2"; withsuite="${3:-yes}"
  {
    echo '[project]'; echo 'name = "fixture"'; echo 'label = "suite"'
    echo 'default_reads = "none"'; echo 'cycles_dir = "claims/cycles"'; echo 'schema = "1"'
    echo; echo '[target]'; echo 'tree = "."'
    echo; echo '[gate]'; echo "traps = \"$traps\""; echo 'quality = "pre-launch"'
    echo; echo '[reads.none]'; echo 'method = "none"'
    [ "$withsuite" = "yes" ] && { echo; echo '[suites.s]'; echo 'dir = "claims/s"'; }
  } > "$d/recurve.toml"
}

if [ -n "${TRAP_FIXTURE:-}" ]; then
  [ -d "$TRAP_FIXTURE/pack" ] || { echo "trap fixture has no pack/ dir"; exit 2; }
  [ -f "$TRAP_FIXTURE/target/recurve.toml" ] || { echo "trap fixture has no target project"; exit 2; }
  [ -f "$TRAP_FIXTURE/ledger-after-install" ] || { echo "trap fixture has no ledger-after-install file"; exit 2; }
  claimed="$(tr -d '[:space:]' < "$TRAP_FIXTURE/ledger-after-install")"
  W="$(mktemp -d)"; cp -R "$TRAP_FIXTURE/." "$W/w"
  ( cd "$W/w/target" && python3 "$RECURVE" --config recurve.toml pack install ../pack --suite imported >/dev/null 2>&1 )
  if [ -f "$W/w/target/claims/imported/gaps.yaml" ]; then actual="yes"; else actual="no"; fi
  rm -rf "$W"
  if [ "$actual" = "no" ] && [ "$claimed" = "yes" ]; then
    echo "install writes drafts only (no ledger) — the receiver must measure; claim of an injected ledger is false"
    exit 1
  fi
  if [ "$actual" = "yes" ] && [ "$claimed" = "yes" ]; then
    echo "ours=install injected a ledger (gaps.yaml) into the receiver oracle=drafts only; the ceremony is the only door"
    exit 1
  fi
  echo "ours=fixture claims ledger-after-install=$claimed, real engine produced $actual oracle=the two must agree"
  exit 1
fi

T="$(mktemp -d)"; trap 'rm -rf "$T"' EXIT

# project A: a baselined suite, exported to a pack.
write_suite "$T/a"; write_config "$T/a" required
( cd "$T/a" && python3 "$RECURVE" --config recurve.toml pack export s --out pack.tgz >/dev/null 2>&1 ) \
  || { echo "ours=pack export failed oracle=a suite exports to a portable pack"; exit 1; }
[ -f "$T/a/pack.tgz" ] || { echo "ours=pack export produced no .tgz oracle=a portable pack file"; exit 1; }

# project B: a different project; install the pack as suite `imported`.
mkdir -p "$T/b/claims/s/probes"
printf '#!/usr/bin/env bash\necho ok; exit 0\n' > "$T/b/claims/s/probes/g-1.sh"; chmod +x "$T/b/claims/s/probes/g-1.sh"
cat > "$T/b/claims/s/gaps.yaml" <<'YAML'
- id: B-0
  title: base suite green by construction
  class: missing-surface
  status: closed
  severity: feature
  reads: none
  covers: [B-0]
  evidence: ["x:1"]
  observed: GREEN by construction
  smallest_fix: none
  probe: probes/g-1.sh
  trap_waiver: fixture
YAML
printf '## B-0\n' > "$T/b/claims/s/GAPS.md"
write_config "$T/b" off

( cd "$T/b" && python3 "$RECURVE" --config recurve.toml pack install "$T/a/pack.tgz" --suite imported >/dev/null 2>&1 ) \
  || { echo "ours=pack install failed oracle=a pack installs into a different project"; exit 1; }

# install brought the probe AND the trap across, and wrote drafts only (no ledger).
[ -f "$T/b/claims/imported/probes/g-1.sh" ] || { echo "ours=install did not carry the probe oracle=probes travel with the pack"; exit 1; }
[ -d "$T/b/claims/imported/probes/g-1.trap" ] || { echo "ours=install did not carry the trap oracle=traps travel with the pack"; exit 1; }
[ -f "$T/b/claims/imported/gaps.draft.yaml" ] || { echo "ours=install produced no draft oracle=claims arrive as drafts"; exit 1; }
[ ! -f "$T/b/claims/imported/gaps.yaml" ] || { echo "ours=install injected a ledger oracle=drafts only; the receiver measures"; exit 1; }

# the receiver measures for itself, then gates the installed suite.
( cd "$T/b" && python3 "$RECURVE" --config recurve.toml baseline imported >/dev/null 2>&1 ) \
  || { echo "ours=baseline of the installed suite failed oracle=the receiver can measure a pack locally"; exit 1; }
[ -f "$T/b/claims/imported/gaps.yaml" ] || { echo "ours=baseline did not promote the installed suite oracle=drafts become observations"; exit 1; }
( cd "$T/b" && python3 "$RECURVE" --config recurve.toml matrix --gate >/dev/null 2>&1 ) \
  || { echo "ours=the installed suite did not gate GREEN in the receiver oracle=exit 0 (re-measured locally)"; exit 1; }

echo "a suite exports to a pack and installs+gates in a different project (probes+traps travel); install writes drafts only — the receiver re-measures"
exit 0

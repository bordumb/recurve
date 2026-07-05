#!/usr/bin/env bash
# AB-13: [gate] governor= is invokable via config alone — the LIVE wiring
# (docs/plans/oracle-strength-and-decorrelation.md R5,
# docs/plans/ablation-infra.md AI2). RED-first: until `recurve decide`
# actually resolves+invokes the configured governor the probe is RED.
#
# Proves this with REAL `recurve decide` subprocess invocations (the exact
# call templates/workflows/burndown.sh's stop_verdict() makes) over a tiny
# fixture project — no manual Python wiring, no mocked decide() call.
#
# With $TRAP_FIXTURE: a scenario asserting governor=mechanical_review with
# no RECURVE_GOVERNOR_CMD configured still reaches STOP-SUCCESS. The real
# engine must refuse (RED = caught).
set -u
ROOT="$(cd "$(dirname "$0")/../../../.." && pwd)"
RECURVE_BIN="$ROOT/recurve"
command -v git >/dev/null || { echo "git unavailable"; exit 2; }

if [ -n "${TRAP_FIXTURE:-}" ]; then
  scenario="$(cat "$TRAP_FIXTURE/scenario" 2>/dev/null || echo "")"
  if [ "$scenario" != "governor_unconfigured_reaches_stop_success" ]; then
    echo "unknown scenario: $scenario"; exit 2
  fi
fi

T="$(mktemp -d)"; trap 'rm -rf "$T"' EXIT
PROJ="$T/proj"
mkdir -p "$PROJ/claims/s/probes/x-1.trap/ce"
cat > "$PROJ/recurve.toml" <<TOML
[project]
name = "ab13-fixture"
label = "suite"
default_reads = "none"
cycles_dir = "cycles"
schema = "1"

[target]
tree = "."

[gate]
traps = "required"
quality = "pre-launch"
governor = "mechanical_review"

[reads.none]
method = "none"

[suites.s]
dir = "claims/s"
TOML
cat > "$PROJ/claims/s/probes/x-1.sh" <<'PROBE'
#!/usr/bin/env bash
if [ -n "${TRAP_FIXTURE:-}" ]; then echo counterexample; exit 1; fi
echo ok; exit 0
PROBE
chmod +x "$PROJ/claims/s/probes/x-1.sh"
echo "x" > "$PROJ/claims/s/probes/x-1.trap/ce/marker"
cat > "$PROJ/claims/s/gaps.yaml" <<'YAML'
- id: X-1
  title: fixture claim
  class: missing-surface
  status: closed
  severity: feature
  reads: none
  evidence: ["x:1"]
  observed: GREEN by construction
  smallest_fix: none
  probe: probes/x-1.sh
YAML
echo "## X-1" > "$PROJ/claims/s/GAPS.md"

cd "$PROJ"
git init -q
EMPTY_HOOKS="$(mktemp -d)"
git config core.hooksPath "$EMPTY_HOOKS"
git config commit.gpgsign false
git add -A
git -c user.name=t -c user.email=t@t commit -q --no-gpg-sign -m initial

NO_VETO_REVIEWER="$T/no_veto_reviewer.py"
cat > "$NO_VETO_REVIEWER" <<'PYEOF'
import json
print(json.dumps({"served_model": "reviewer-model-y", "vetoes": {}}))
PYEOF

VETO_REVIEWER="$T/veto_reviewer.py"
cat > "$VETO_REVIEWER" <<'PYEOF'
import json
print(json.dumps({"served_model": "reviewer-model-y",
                  "vetoes": {"X-1": "review-tier objects: found a real disagreement"}}))
PYEOF

if [ -n "${TRAP_FIXTURE:-}" ]; then
  # A broken decide-wrapper that treats "governor could not be consulted at
  # all" (no RECURVE_GOVERNOR_CMD configured) as "cleared" instead of
  # "pending" — governor=mechanical_review configured, no command wired.
  # The real engine must never silently reach STOP-SUCCESS here.
  unset RECURVE_GOVERNOR_CMD
  OUT="$(AB13_ENGINE_ROOT="$ROOT" RECURVE_ACTOR_MODEL=actor-model-x \
        python3 "$TRAP_FIXTURE/broken_decide_wrapper.py" 2>&1)"
  if [ "$OUT" = "STOP-SUCCESS" ]; then
    echo "ours=$OUT oracle=must NOT be STOP-SUCCESS with no governor command configured "\
         "— correctly caught the silent-fallback bug"
    exit 1
  fi
  echo "ours=$OUT oracle=expected STOP-SUCCESS (this fixture did not exercise the intended bug)"
  exit 0
fi

# --- no TRAP_FIXTURE: the real positive assertions -------------------------

fail() { echo "FAIL: $1"; exit 1; }

# 1. a clean, cross-identity review-tier pass -> the real `recurve decide`
# (no manual Python wiring — a real subprocess, the exact invocation
# burndown.sh's stop_verdict() makes) reaches STOP-SUCCESS.
OUT1="$(RECURVE_ACTOR_MODEL=actor-model-x RECURVE_GOVERNOR_CMD="python3 $NO_VETO_REVIEWER" \
       python3 "$RECURVE_BIN" decide --open 0 --regressed 0 --broken 0 --uncovered 0)"
[ "$OUT1" = "STOP-SUCCESS" ] || fail "clean review-tier pass -> got '$OUT1', want STOP-SUCCESS"

# 2. a vetoing review-tier pass -> STOP-SUCCESS actually depends on the real
# verdict: it must NOT be STOP-SUCCESS.
OUT2="$(RECURVE_ACTOR_MODEL=actor-model-x RECURVE_GOVERNOR_CMD="python3 $VETO_REVIEWER" \
       python3 "$RECURVE_BIN" decide --open 0 --regressed 0 --broken 0 --uncovered 0)"
[ "$OUT2" != "STOP-SUCCESS" ] || fail "vetoing review-tier pass -> got STOP-SUCCESS, must not"
[ "$OUT2" = "CONTINUE" ] || fail "vetoing review-tier pass -> got '$OUT2', want CONTINUE"

# 3. a non-green vector never even attempts to consult the governor (the
# mechanical/gate layer takes priority) — CONTINUE regardless.
OUT3="$(RECURVE_ACTOR_MODEL=actor-model-x RECURVE_GOVERNOR_CMD="python3 $VETO_REVIEWER" \
       python3 "$RECURVE_BIN" decide --open 1 --regressed 0 --broken 0 --uncovered 0)"
[ "$OUT3" = "CONTINUE" ] || fail "open work present -> got '$OUT3', want CONTINUE"

# 4. governor="off" (a sibling fixture) is untouched — the exact pre-R5
# behavior, byte for byte.
PROJ_OFF="$T/proj_off"
cp -R "$PROJ" "$PROJ_OFF"
sed -i.bak 's/governor = "mechanical_review"/governor = "off"/' "$PROJ_OFF/recurve.toml"
cd "$PROJ_OFF"
OUT4="$(RECURVE_GOVERNOR_CMD="python3 $VETO_REVIEWER" python3 "$RECURVE_BIN" decide \
       --open 0 --regressed 0 --broken 0 --uncovered 0)"
[ "$OUT4" = "STOP-SUCCESS" ] || fail "governor=off -> got '$OUT4', want STOP-SUCCESS unaffected"
cd "$PROJ"

# 5. structural proof of "zero changes to the loop": the SHIPPED
# burndown.sh template's stop_verdict() still calls exactly
# `$PROG decide --open ... --regressed ... --broken ... --uncovered ...`
# (optionally --divergent) — no new flag was added for the governor to
# reach it; config alone is what changed its behavior above.
BURNDOWN="$ROOT/templates/workflows/burndown.sh"
[ -f "$BURNDOWN" ] || fail "no shipped burndown.sh template at $BURNDOWN"
grep -A3 'stop_verdict()' "$BURNDOWN" > /dev/null || true
grep -q '\$PROG decide --open' "$BURNDOWN" || fail "stop_verdict() no longer calls \$PROG decide"
grep -qE '\$PROG decide --open "\$\{open:-0\}" --regressed "\$\{regressed:-0\}" --broken "\$\{broken:-0\}" --uncovered "\$\{uncovered:-0\}"' "$BURNDOWN" \
  || fail "stop_verdict()'s \$PROG decide call changed shape — the live wiring must need zero loop changes"

# 6. the REAL, unmodified shipped stop_verdict() bash function, sourced
# directly (not re-implemented), against the fixture project — the
# strongest available proof short of spawning a live agent cycle.
STOP_VERDICT_SRC="$(sed -n '/^stop_verdict()/,/^}/p' "$BURNDOWN")"
NEXT_JSON='{"recommended": null, "then": [], "review_gated": []}'
RUN_STOP_VERDICT="$T/run_stop_verdict.sh"
{
  echo '#!/usr/bin/env bash'
  echo "PROG=\"python3 $RECURVE_BIN\""
  echo 'py() { python3 -c "$1" "${@:2}"; }'
  echo "$STOP_VERDICT_SRC"
  echo "stop_verdict '$NEXT_JSON'"
} > "$RUN_STOP_VERDICT"
OUT6="$(RECURVE_ACTOR_MODEL=actor-model-x RECURVE_GOVERNOR_CMD="python3 $NO_VETO_REVIEWER" \
       bash "$RUN_STOP_VERDICT" 2>/dev/null | tail -1)"
[ "$OUT6" = "STOP-SUCCESS" ] || fail "the real, sourced stop_verdict() -> got '$OUT6', want STOP-SUCCESS"
OUT7="$(RECURVE_ACTOR_MODEL=actor-model-x RECURVE_GOVERNOR_CMD="python3 $VETO_REVIEWER" \
       bash "$RUN_STOP_VERDICT" 2>/dev/null | tail -1)"
[ "$OUT7" != "STOP-SUCCESS" ] || fail "the real, sourced stop_verdict() with a veto -> got STOP-SUCCESS, must not"

echo "[gate] governor= is invokable via config alone: a real 'recurve decide' subprocess "\
     "(the exact call burndown.sh's stop_verdict() makes, and the REAL sourced stop_verdict() "\
     "function itself) resolves mechanical_review through the registry, invokes it, and "\
     "STOP-SUCCESS genuinely depends on its verdict — zero changes to the loop"
exit 0

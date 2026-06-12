#!/usr/bin/env bash
# PS-1: p99 latency under the SLO. Warmup, N samples, p99 not mean, rig in
# the output. Configure: PACK_CMD, PACK_P99_MS (PACK_N optional).
if [ -n "${TRAP_FIXTURE:-}" ]; then
  CMD="bash $TRAP_FIXTURE/slow.sh"
  THRESH="50"
  N="${PACK_N:-10}"          # the counterexample is deliberately slow; keep the audit quick
elif [ -z "${PACK_CMD:-}" ] || [ -z "${PACK_P99_MS:-}" ]; then
  echo "PACK_CMD/PACK_P99_MS not set — cannot measure"; exit 2
else
  CMD="$PACK_CMD"
  THRESH="$PACK_P99_MS"
  N="${PACK_N:-200}"
fi
python3 - "$THRESH" "$N" $CMD <<'PYEOF'
import subprocess, sys, time
thresh = float(sys.argv[1]); n = int(sys.argv[2]); cmd = sys.argv[3:]
for _ in range(5):
    subprocess.run(cmd, capture_output=True)
times = []
for _ in range(n):
    t0 = time.perf_counter()
    subprocess.run(cmd, capture_output=True)
    times.append((time.perf_counter() - t0) * 1000)
times.sort()
p99 = times[max(0, int(0.99 * len(times)) - 1)]
print(f"rig: N={n} warmup=5 p99={p99:.1f}ms threshold={thresh}ms")
if p99 > thresh:
    print(f"ours=p99 {p99:.1f}ms oracle=p99 <= {thresh}ms")
    sys.exit(1)
sys.exit(0)
PYEOF

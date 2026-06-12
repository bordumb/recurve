# perf-slo — a latency promise with a number in it

> **Reader:** a human installing this pack. Set `PACK_CMD` and `PACK_P99_MS`,
> then baseline. Perf probes follow the discipline: warmup, N≥100 samples,
> p99 not mean, the rig printed in the output (a number without its rig is
> not a measurement).

## Conventions

- "fast" is not a claim; "p99 ≤ <N>ms on <rig>" is. The threshold lives in
  config/env, never in prose alone.
- A flapping perf probe is quarantined, never averaged into GREEN — see the
  engine's probe contract.

## 1. command p99 latency stays under the SLO

Observable: across N warm runs, the 99th-percentile wall-clock of
`$PACK_CMD` is ≤ `$PACK_P99_MS` milliseconds, and the probe prints the rig
line (`N=… warmup=… p99=… threshold=…`). Negative space: a run over
threshold is RED with the measured p99 as the one line of truth.

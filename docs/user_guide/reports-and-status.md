# Reports & status

recurve writes down everything the loop does, so you never have to trust a
transcript. Three surfaces read that record back to you: a one-glance health
check, a deterministic run report, and the run-record statistics.

## Status — one-glance health

```bash
recurve status          # open/closed counts, the true gate verdict, drafts pending
recurve status --gate   # same, but exit nonzero if the gate does not pass (for CI)
```

`status` computes the gate verdict from a full matrix run — never a cached
number — so `PASS` means every closed claim's probe is still GREEN right now.
Any `broken`, `stale`, or `failed-trap` trouble is surfaced on its own line.

```
recurve — health
  claims     0 open · 145 closed
  gate       PASS
```

## Reports — the deterministic run report

After every cycle the loop appends a free, deterministic report to
`.recurve/state/reports/<run-id>.md`. You can also render it on demand:

```bash
recurve report                     # to stdout
recurve report --out report.md     # append to a file
recurve report --format json       # the same data, machine-readable
```

The report has no narrator and touches no network. It covers:

- **Progress** — closed / open / parked counts by suite, class, and severity,
  plus the remaining workable count.
- **Cycle durations** — mean, median, the last-5 trend, and an ETA projection
  from the last closed cycles (bounds stated; "insufficient data" under two).
- **Diff honesty** — over the range the records cover: lines added/removed,
  files touched, an honesty scan counting added lines that match the configured
  suppression markers, and a "review before signing" list for the largest diffs
  touching sensitive paths.

### Optional narration

```bash
recurve report --narrate    # pipe the report + records through [report] narrator
```

`--narrate` sends the rendered report and the cycle records to whatever LLM
command you configure as `[report] narrator` and appends its prose under a
`## Narrative` heading. The judgment costs whatever your narrator costs; the
numbers stay free and deterministic. A narrator that fails or times out costs
only the prose — the report still renders.

## Statistics — the run-record dataset

```bash
recurve stats       # close rates, attempts, cost — from the run records
recurve ledger      # every claim and its current status
recurve next        # what the loop will pick next, and why
```

`stats` reports budget-attached close rates (raw alongside close-rate-at-1 and
close-rate-at-2 attempts) and surfaces verification debt — closed claims whose
probe the drill cannot audit — beside the rates it qualifies.

For the full run-record schema, the branch-capture fields, and how the log
exports as a training-ready dataset, see
[Run data & trajectories](run-data.md).

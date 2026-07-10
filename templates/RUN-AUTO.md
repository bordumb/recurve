# RUN-AUTO — unattended operation addendum

You are the operator starting an unattended burndown on **{{PROJECT}}**. Your
first action: read .recurve/RUN.md (the per-cycle contract), then start the
loop. The simplest way:

```bash
{{PROG}} run                 # agent defaults to a bypass-permissions Claude; --dry-run to preview
```

`{{PROG}} run` is a thin wrapper over the stamped workflow — it fills in a
bypass-permissions agent (an unattended cycle cannot answer a permission prompt,
and the loop is a cage: write boundary, per-cycle rollback, tree lock, the gate
decides) and the cap, then execs `.recurve/workflows/burndown.sh`. To drive the
workflow yourself, set the agent explicitly:

```bash
AGENT_CMD='claude -p --permission-mode bypassPermissions' bash .recurve/workflows/burndown.sh
```

Your stop condition: the loop halts itself.

## Before you start

- `{{PROG}} validate && {{PROG}} matrix --gate` must both be green. An
  unattended run started on a broken baseline burns every cycle on the same
  rock. (Keep this *baseline* gate **uncached** — ground truth.)
- **Speed knob for the run:** the per-cycle gate may use `{{PROG}} matrix --gate
  --cache` (see RUN.md — a sound, faster full gate that skips probes whose inputs
  are unchanged). On a long unattended run this is the single biggest lever on
  wall-clock, since each probe otherwise cold-loads its whole build environment.
  Keep the baseline gate above and **one final uncached `{{PROG}} matrix --gate`
  before the run reports** — the definitive verdict the run is recorded against.
- `{{PROG}} lock status` must say unlocked. Two loops on one tree corrupt
  both; the loop refuses to start if a lock is held. If the holder is
  confirmed dead, a human runs `{{PROG}} lock steal` — never automate this.
- Keep the machine awake for the duration (on laptops, a keep-awake tool);
  a sleeping machine reads as a hung agent to any watchdog.
- Commit policy is **{{COMMIT_POLICY}}** — verify the loop can commit without
  any prompt (signing prompts hang headless agents; that is why unsigned
  per-cycle commits exist).
- **Skim the drafts before launching.** The loop arms successive waves from
  `gaps.draft.yaml` on its own; starting it IS your sign-off that every
  pending draft deserves a probe. Forks are still respected: while
  ADJUDICATE.md has a pending DECIDED line, the loop refuses to arm and
  halts for you instead.

## The loop's own guarantees (you do not babysit these)

- **Wave arming:** when the strict ledger empties but drafts pend, an
  arming agent authors probes + traps for the next batch (`WAVE` per round,
  `ARM_WAVES` rounds max, security-tradeoff drafts always skipped), then
  `baseline` measures them for real and promotes RED ones as open work.
  The run continues until spec exhaustion, not wave exhaustion.
- **Park-and-continue:** an un-greenable gap is parked with an attempt
  journal; the loop moves on. It halts only on: backlog and drafts both
  empty, pending adjudications, the cycle cap, the wave limit, an arming
  that opens no work, {{MAX_FAILS}} consecutive failures, or {{RUNAWAY}}
  consecutive net-gap-positive cycles (runaway scope).
- **Per-cycle commits** mean a dead run loses at most one cycle's work.
- **Timed-out agents count as failed cycles**, not hangs.

## Resume after a kill / crash / sleep

1. `git log` — per-cycle commits show exactly which cycles landed.
2. `{{PROG}} matrix` — trust only the gate, not the dead run's logs.
3. A half-written cycle (sculpt without gate) is reverted by consulting the
   last cycle snapshot diff — never by `git reset` on shared state.
4. Restart the loop; it re-derives everything from the ledger. Seed
   `--parked` with still-stuck gaps from `{{PROG}} park`.

## When it finishes

Read the wrap-up record (`.recurve/state/records.jsonl`): ledger delta, parked
list with reasons, the review queue. Each cycle also appended a deterministic
run report to `.recurve/state/reports/<run-id>.md` — progress, durations, the
ETA projection, and the diff honesty scan; read it before signing anything
(`{{PROG}} report --narrate` adds narrator prose, if one is configured). The
human queue is ranked: adjudications first, then review-gated promotions, then
parked triage.

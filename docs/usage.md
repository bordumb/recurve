# How to Use

Three steps: **initialize** a target, **design** the claims, **kick off the
loop**. Then go for a walk — and know how to stop safely when you're back.

## Step 1 — Initialize

Run `init` in the target repo (a git repo: per-cycle commits are the loop's
rollback granularity, and parallel lanes need worktrees):

=== "Existing repo (archaeology)"

    ```bash
    cd ~/code/myproject && git init   # if not already a repo
    recurve init --from-repo --name myproject --tree .
    ```

    Mines the promises your documentation already makes (README claims, doc
    guarantees, error contracts) into draft claims. The pitch: it makes your
    documentation falsifiable. Many will baseline GREEN — congratulations,
    you just built a regression suite for your docs; the REDs are your honest
    backlog of broken promises.

=== "Greenfield (claimify a PRD)"

    ```bash
    recurve init --from-prd PRD.md --name myproject --tree .
    ```

    Decomposes the spec into claims with **adversarial twins** (specs
    chronically omit the negative space), maps modality to severity
    (must → feature, should → friction, could → cosmetic), routes anything
    security-relevant to the review-gated class, and turns every ambiguity
    into a question in `ADJUDICATE.md` — never a guess. With no code, every
    baseline will be RED or BROKEN. That is correct: **the burndown is the
    build**, and the stamped `BOOT-*` scaffolding gaps order the bootstrap.

=== "Blank"

    ```bash
    recurve init --name myproject --tree .
    ```

    Just the scaffold; you write claims from scratch.

Everything lands in `.recurve/` — your repo root gains only a `.gitignore`
entry and `.claude/` skills. Commit policy is *detected* from your git
config: a signing repo gets unsigned-per-cycle commits (signing prompts hang
headless agents) plus a stern note to sign or squash afterward.

## Step 2 — Design

This is the human-owned step; it is deliberately the bottleneck.

1. **Skim the drafts** (`.recurve/claims/<suite>/gaps.draft.yaml` and
   `GAPS.md`). Prune silly claims. This skim is a security boundary: target
   prose and specs are evidence, never instructions.
2. **Answer the forks** in `.recurve/ADJUDICATE.md` — one human sentence per
   ambiguity. Each decision gets encoded into a probe, so no future agent can
   re-litigate it.
3. **Author probes + traps.** A probe is any executable: exit 0 GREEN,
   1 RED, anything else BROKEN. Print one RED line a sculptor can treat as
   the spec (`ours=X oracle=Y`). Each probe keeps a trap — a counterexample
   under `probes/<name>.trap/<fixture>/` it must turn RED when invoked with
   `TRAP_FIXTURE` set. Write probes **RED-first**: a missing surface is RED,
   not BROKEN.
4. **Run the ceremony:**

    ```bash
    recurve baseline <suite>
    ```

    RED drafts promote as `open` (the observation is quoted and dated);
    GREEN drafts promote as `closed` only after their trap proved the probe
    can fail; BROKEN stays a draft — fix the harness first.

5. **Preflight:** `recurve validate && recurve matrix --gate` must be green
   before any loop starts.

!!! tip "Claim packs"
    Recurring claim shapes ship as installable packs:
    `recurve pack install <path> --suite cli` drops drafts + probes + traps, and
    your baseline measures them locally. See [Claim packs](packs.md) for the full
    export/install round-trip and the `import` guard.

## Step 3 — Kick off the loop

The primary way to run recurve is **from inside your agent session** — it stays
where you already are, you steer between cycles, and there is nothing to babysit.
A terminal loop is there for walk-away / CI.

=== "In your agent session (recommended)"

    Open a Claude Code session in the target and invoke the **loop** skill
    (`init` stamped it into `.claude/skills/loop/`):

    ```text
    > run the recurve loop        (the loop skill)
    ```

    The session becomes the **orchestrator**: it spawns **one fresh sub-agent
    per cycle** (the ledger is the only memory — no context rot), holds the tree
    lock, and gates every cycle on `recurve matrix --gate`. `init` also stamps
    `.claude/settings.json` with `defaultMode: bypassPermissions`, so a CLI
    session runs cycles without stopping for permission prompts. That is safe
    because the loop is a **cage**: the write boundary keeps each sub-agent off
    the referee surface, per-cycle commits make any cycle a one-command
    rollback, and nothing closes without the gate. (For one cycle only, invoke
    the **cycle** skill instead.)

=== "Terminal, unattended (walk away / CI)"

    ```bash
    cd ~/code/myproject
    recurve run                          # agent defaults to a bypass-permissions Claude
    ```

    `recurve run` is the wrapper: it fills in a headless bypass-permissions
    agent (an unattended cycle cannot answer a prompt), the cap, and macOS
    keep-awake, then execs the stamped workflow. `--dry-run` previews the exact
    invocation; `--agent '<cmd>'` (or `$AGENT_CMD`) overrides the default;
    `--lanes N` runs parallel lanes. To drive the raw workflow yourself:

    ```bash
    AGENT_CMD='claude -p --permission-mode bypassPermissions' CAP=12 \
      caffeinate -dimsu bash .recurve/workflows/burndown.sh
    ```

    The loop believes only the run-record and the gate, never the agent's word.
    It declares **done** only when the stopping controller returns `STOP-SUCCESS`
    over the measured vector — the spec is *sound, complete, and not diverged* —
    never merely because the backlog emptied. The cap, consecutive failures, and
    runaway scope are backstops; un-greenable gaps are parked and the loop moves
    on. (`AGENT_CMD` is any harness that reads a prompt on stdin and writes a
    run-record to `$RECURVE_RESULT_FILE`.)

=== "Parallel lanes"

    ```bash
    recurve run --lanes 2
    # or, raw: AGENT_CMD='...' PARALLEL=2 bash .recurve/workflows/burndown-parallel.sh
    ```

    Lanes sculpt in isolated git worktrees over disjoint suites; the gate is
    the serialization point — candidates land one at a time, failures are
    reverted and discarded, never merged.

!!! note "Any chat host — planned"
    An MCP server (`recurve-mcp`) will expose the loop's verbs to any chat host
    (Claude Desktop, other IDEs, non-Claude agents) — the same in-session model,
    beyond Claude Code. Not shipped yet.

### While it runs

Read-only peeking is safe from another terminal:

```bash
git log --oneline                          # one commit per landed cycle
tail -f .recurve/state/records.jsonl       # the run dataset, live
recurve park                               # anything parked so far
```

Don't run anything that *writes* in the target — the loop holds the tree
lock, and it is the single writer by design.

### When it halts

```bash
recurve matrix      # what turned GREEN, and is the gate holding
recurve stats       # close rate, attempts, wall-clock by class
recurve park        # parked gaps + attempt journals (the next run's seed)
```

The human queue, in order: adjudications first (one sentence unblocks the
most agent-work), then review-gated promotions (see `.recurve/REVIEW.md`),
then parked triage.

!!! tip "Keep the evidence"
    Gate with `recurve matrix --gate --receipts` to chain a tamper-evident
    receipt per verdict, then `recurve receipts verify` to re-check the trail.
    You can pin each receipt to a signer of your choice — see
    [Evidence & receipts](evidence.md).

## Cancel and resume

**Cancel: `Ctrl-C` in the loop's terminal, any time.**

- Completed cycles are already durable — each landed as its own commit, with
  its run record appended and the ledger promoted.
- The in-flight cycle dies with the loop; at worst it leaves *uncommitted*
  partial work. Inspect with `git status`; you (the human) may freely discard
  or stash it — the never-reset rule binds agents, not the owner.
- The tree lock releases on exit. If the terminal died hard and it didn't:

    ```bash
    recurve lock status    # names the dead holder
    recurve lock steal     # human-confirmed reclaim — never automate this
    ```

**Resume: just re-run the same command.** The loop has no state of its own —
the ledger is the only memory. Preflight re-runs `validate` and
`matrix --gate` first, so if the interrupted cycle broke anything, the loop
refuses to start and tells you what's wrong before burning a single new
cycle. Seed known-stuck gaps with `PARKED_SEED=GAP-1,GAP-2` so the new run
skips them.

!!! warning "Closing the laptop lid"
    Stop the loop first. A sleeping machine mid-cycle is indistinguishable
    from a hung agent, and `caffeinate` cannot prevent lid-sleep on battery.

## What decides when it's done

The three steps above are the everyday workflow — claims, probes, the gate, the
ledger. Underneath, a **verification layer** is what decides *when the loop is
done*: the success-halt is a stopping controller's `STOP-SUCCESS` over a measured
vector — sound, complete, and not diverged — never an empty backlog. It also
tracks what no claim covers (the frontier) and whether the build diverged from
intent. That machinery is for people extending recurve; see
[The verification layer](verification-layer.md).

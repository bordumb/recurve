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
    `recurve pack install <path-to-pack> --suite cli` drops drafts + probes +
    traps; your baseline measures them locally. Packs never touch the ledger
    directly.

## Step 3 — Kick off the loop

=== "Unattended (walk away)"

    ```bash
    cd ~/code/myproject
    export PATH="$PWD/bin:$PATH"          # however recurve reaches your PATH
    AGENT_CMD='claude -p --permission-mode bypassPermissions' CAP=12 \
      caffeinate -dimsu bash .recurve/workflows/burndown.sh
    ```

    `AGENT_CMD` is any agent harness that reads a prompt on stdin and writes
    a run-record JSON to `$RECURVE_RESULT_FILE` — the loop believes only the
    record and the gate, never the agent's word. Watchdogs halt on: no work
    left, the cap, consecutive failures, or runaway scope. Un-greenable gaps
    are parked with attempt journals; the loop moves on.

    (`caffeinate` is macOS keep-awake; a sleeping machine looks like a hung
    agent.)

=== "One cycle by hand"

    Follow `.recurve/RUN.md` — it is the entrypoint and the stop condition.
    Short form: `recurve next`, sculpt the smallest honest change, rebuild,
    `recurve matrix --gate`, promote open→closed + rewrite the prose,
    snapshot, commit, `recurve record append`, **stop**. One cycle = one
    agent.

=== "Parallel lanes"

    ```bash
    AGENT_CMD='...' PARALLEL=2 bash .recurve/workflows/burndown-parallel.sh
    ```

    Lanes sculpt in isolated git worktrees over disjoint suites; the gate is
    the serialization point — candidates land one at a time, failures are
    reverted and discarded, never merged.

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

## Multi-tree: build one tree, sculpt another

Some loops live in two repos: a **scaffold** you build — a frontend, a demo, a
conformance suite — that *exercises* a **platform** in another repo, where the
honest fix for a gap the scaffold reveals is to harden the platform. recurve
models this directly. A config declares one primary `[target]` (the tree the
loop builds) plus zero or more `[sculpts.<name>]` (secondary trees, in other
repos, the loop may sculpt when a claim demands it):

```toml
[target]                                  # the PRIMARY tree the loop BUILDS
tree = "web"
forbidden_strings = ["GAP-", "FE-", "recurve"]
rebuild = "npm ci && npm run build"

[sculpts.platform]                        # a SECONDARY tree in another repo
tree = "../auths"
branch = "dev-platform"                   # its commits land here
forbidden_strings = ["GAP-", "recurve"]   # its OWN leak vocabulary
rebuild = "cargo build --release"
gate = "cargo test && ../demos/rictl matrix --gate"   # its OWN gate, federated
```

**`[target]` is what you build; `[sculpts.*]` is what you feed.** When a claim's
honest fix is in a sculpt tree, the cycle sculpts there and commits to that repo
on its own branch — one commit per repo touched, never a cross-tree change in
one commit. Each tree carries its own `forbidden_strings`, so loop vocabulary is
kept out of every product the loop touches.

The gate **federates**: `recurve matrix --gate` is green only when the target's
probes pass **and** every declared sculpt's own `gate` command exits zero. A
sculpt that breaks the platform's gate turns the federated gate red even if the
scaffold's own probes are green — so a scaffold can never "pass" by hardening
itself while regressing the platform it feeds.

With no `[sculpts.*]`, a config is exactly single-tree; federation is opt-in and
costs nothing until you declare a sculpt.

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

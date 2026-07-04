# Claude skill

If you use **Claude Code**, `recurve install` drops two global slash commands
into `~/.claude/skills/` that wrap the whole workflow with a guided prompt — so
you never have to touch the raw CLI unless you want to. They work in any repo,
with no per-repo setup.

Under the hood they run exactly the verbs on the
[Provider-agnostic](usage-provider-agnostic.md) page — nothing here is a
different engine, just an ergonomic front door.

## Install

From a clone of the recurve repo:

```bash
pip install -e .        # or: pipx install .   (installs the `recurve` CLI)
recurve install         # links the binary AND installs the two skills
```

`recurve install` prints `installed global skills into …: /recurve-plan,
/recurve-work`. So a fresh clone is one line:

```bash
git clone https://github.com/bordumb/recurve.git && cd recurve
pip install -e . && recurve install
```

(`recurve install --no-skills` links only the binary; `--skills-dir DIR`
installs the skills somewhere other than `~/.claude/skills`.)

## `/recurve-plan` — get to a gate-ready plan

Run it in the target repo. It walks you through, stopping at the checkpoints:

1. **verifies** the `recurve` CLI is on PATH (and tells you how to install it if not);
2. **initializes** the repo (`recurve init`) if it isn't already;
3. **finds or interviews you into** a `docs/PRD.md` — kept decomposition-oriented,
   because claims get carved from it;
4. drives that PRD through the **admission gate** (`recurve admit`) — recurve's
   front-door check for *"is this goal concrete enough to become falsifiable
   claims?"* — working its interview worklist with you until it passes.

You end with an initialized repo and a PRD that is ready to build claims from.

## `/recurve-work` — burn down under the gate

Run it after `/recurve-plan`. It:

1. checks the baseline is clean (`recurve validate` / `matrix --gate` / `lock status`);
2. if the **ledger is empty**, offers to author the first claims from the PRD
   (RED-first probes + traps, then baseline) — so it never runs on an empty backlog;
3. **asks how you want to run** —
    - **Endless** — cycle after cycle until the gate is complete, goes red, or hits a dead-end;
    - **Per-claim** — stop after each claim closes so you review and approve the next;
4. drives the loop with the hard rules baked in: the gate is the arbiter, never
   fake or weaken a probe, per-cycle commits.

## What you don't give up

The skills are a convenience layer, not a lock-in. The same repo is fully
drivable from the [CLI](usage-provider-agnostic.md) by **any agent**
(`$AGENT_CMD`) or a **human** following `RUN.md`. Claude Code just gets a nicer
door — the evidence, the gate, and the ledger are identical either way.

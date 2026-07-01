# Command improvements — the "Stripe of agent loops"

> Internal design note (stays in `docs/plans/`, never published). Goal: close the
> gap between recurve's *power* and its *felt simplicity* — make it feel like
> Stripe (a tiny surface hiding vast machinery, with great defaults) **without
> diluting the epistemics that are the whole point.**

## The itch

The homepage now leads with a three-command Quick Tour and an install that is
still `clone → pip install → symlink`. That is *honest*, but it is not
*effortless*. Two things still leak machinery onto the newcomer:

- The loop is a shell incantation — `AGENT_CMD='…' CAP=12 caffeinate -dimsu bash
  .recurve/workflows/burndown.sh` asks you to hold five concepts (an env var, the
  agent contract, a cap, a keep-awake wrapper, a stamped script path) before a
  single cycle runs.
- The surface is ~two dozen verbs. A first-timer cannot tell the four they need
  from the nineteen they don't.

Stripe's trick was never "fewer features" — it was **a surface you can hold in
your head, with the hard parts hidden until you reach for them.** This note is
how recurve gets there.

## The Stripe test (north star)

Three concrete bars. If we hit these, it *feels* like Stripe:

1. **One line to try it.** `recurve demo` proves the loop end-to-end in under two
   seconds — zero setup, no config, no agent, no network.
2. **One line to run it.** `recurve run` drives the burndown. No env-var
   incantation, no path to a bash script.
3. **A surface you can hold in your head.** A newcomer meets ~5 verbs, not ~23.
   The rest is there the moment they reach for it.

## What's heavy today (honest inventory)

| Weight | Where it shows up |
| --- | --- |
| **Verb sprawl** | ~23 subcommands: `ledger show validate next probe matrix report freshness coverage review import cycle baseline park init install record lock receipts stats pack adjudicate drill`. Most are power tools; nothing signals which are the core. |
| **The loop is a script** | `AGENT_CMD='…' bash .recurve/workflows/burndown.sh` — the loop, recurve's headline capability, is not a verb. |
| **Multi-step install** | `git clone` → `pip install pyyaml` → `recurve install`. No `pipx install recurve`, no `curl \| sh`, no `brew`. |
| **Config-first** | `recurve.toml` is required (discovery walks up from cwd). There is no zero-config path. |
| **The design bottleneck** | `claimify` emits *prose* drafts; every probe still starts from a blank file + an empty trap dir. |
| **The verification layer is invisible** | `admission / completeness / fidelity / controller / runtime` exist as library APIs — the strongest guarantees recurve has are unreachable without writing Python. |

## The one line that governs everything: incidental vs essential

recurve's *value* is the epistemic ceremony — the baseline door, required traps,
the fleet gate, human-owned claims, "evidence not belief." Simplicity work must
cut **incidental** overhead and never touch **essential** overhead.

- **Incidental (cut it):** verb sprawl, env-var incantations, config boilerplate,
  multi-step install, blank-file probe authoring, a library-only verification layer.
- **Essential (keep it — but make it feel effortless):** the human owns the
  claims; probes are RED-first; every probe keeps a trap; the gate is the only
  arbiter; BROKEN blocks; adjudication is human.

The mantra: **make the machinery invisible, not absent.**

## Proposed surface (before → after)

Collapse ~23 flat verbs into ~5 **core** + three **namespaces**. Keep the old
flat verbs as hidden aliases for one release so nothing breaks.

| Core verb | Intent | Absorbs today's |
| --- | --- | --- |
| `recurve init <path>` | start from a spec or a repo | `init` (+ zero-config inference) |
| `recurve run` | run the burndown loop | the `burndown.sh` incantation |
| `recurve status` | one glance: backlog + gate + progress | `ledger` + `matrix` verdict + `stats` |
| `recurve gate` | the one CI command | `matrix --gate` |
| `recurve demo` | prove the loop in <2s | *(new)* |

| Namespace | Holds |
| --- | --- |
| `recurve claims …` | `baseline import pack adjudicate review show validate coverage` |
| `recurve loop …` | `next park record lock cycle` |
| `recurve audit …` | `matrix freshness receipts stats drill report` |

Default `--help` lists the five core verbs; `recurve help --all` reveals the rest.

## Concrete proposals

Each: **what · why · refactor size · risk · how it's gated.** (recurve is built by
dogfooding, so "gated" means a claims suite with probes + traps, graduated via
`recurve baseline` and enforced by `recurve gate` — the same discipline it sells.)

**P1 — `recurve run` (wrap the loop).** A verb that resolves the agent
(`--agent` flag › `AGENT_CMD` env › config › autodetect), defaults `CAP`, wraps
`caffeinate` on macOS, and routes `--lanes N` to the parallel workflow. *Why:* the
headline capability should be a verb, not a script path. *Size:* S–M. *Risk:* low
(pure ergonomics over existing `burndown.sh`). *Gate:* a `run` suite — probe: a
canned agent drives a temp target RED→GREEN via `recurve run`; trap: a `run` that
ignores `CAP` or bypasses the gate.

**P2 — `recurve status` (one glance).** Merge the red backlog, the gate verdict,
and the progress vector into a single view. *Why:* today you run three commands to
answer "where am I?" *Size:* S. *Risk:* low. *Gate:* probe: `status` reports the
open count + gate verdict + frontier size; trap: a `status` that prints "all good"
while a probe is BROKEN (no greenwashing).

**P3 — `recurve demo` (sign-of-life).** A bundled micro-suite (2–3 real claims,
real probes + traps) that scaffolds into a scratch dir, baselines, gates, and
prints a RED→GREEN transition — under two seconds, no network, no agent, no
config. *Why:* the fastest way to *understand* recurve is to watch one cycle.
*Size:* M. *Risk:* low. *Gate:* probe: `recurve demo` exits 0 and shows a RED→GREEN
flip in a temp dir; trap: a demo that writes into cwd or needs a network/agent.

**P4 — verb grouping + progressive `--help`.** argparse subparser namespaces;
default help shows the five core; hidden aliases keep old verbs working one
release. *Why:* the surface a newcomer sees is the surface they must reason about.
*Size:* M. *Risk:* low–medium (touches every subparser). *Gate:* extend the
CLI-contract pack — every advertised verb runs; every hidden alias still resolves.

**P5 — zero-config `init`.** Positional `recurve init <PRD.md | repo | .>`; infer
the mode (file → claimify, git dir → archaeology, empty → blank), the suite name
(from the spec/dir), and `tree`/`rebuild`. Still writes `recurve.toml` — you just
never had to think about it. *Why:* config-first is the classic adoption tax.
*Size:* M. *Risk:* medium (inference can guess wrong — so it must **announce what
it inferred**). *Gate:* probe: `recurve init ./PRD.md` yields a valid config +
draft suite with no flags; trap: an inference that silently picks the wrong mode.

**P6 — one-line install.** Publish to PyPI so `pipx install recurve` works;
optionally a `curl -sSfL …/install.sh | sh`. *Why:* the Stripe feel starts at
install; `brew install` / `curl | sh` is the bar. *Size:* M (packaging/release,
**not** engine). *Risk:* low technically; it is a **human decision** (owner, name,
cadence). *Gate:* a smoke suite — a fresh env `pipx install`s and `recurve demo`
passes.

**P7 — surface the verification layer.** Give `admission / completeness /
fidelity / controller` real verbs (`recurve admit <goal>`, `recurve frontier`);
`recurve run` already *senses* them internally. *Why:* recurve's strongest
guarantees should be first-class, not library-only. *Size:* L. *Risk:* medium.
*Gate:* the existing admission/completeness/fidelity/stopping suites + new CLI
probes wrapping them.

## The design bottleneck (the overhead that is *not* incidental)

The human authoring claims + probes + traps is where "evidence not belief" is
paid for. **Do not automate it away — lower its friction:**

- `claimify` emits **runnable probe scaffolds** — RED-first stubs with the trap
  directory already laid out — so "author a probe" becomes "fill in the oracle,"
  not "start from a blank file."
- an agent-assisted `recurve draft` that *proposes* probes + traps, but every
  proposal must pass the **admission** gate (is it probe-able?) and an
  **adversarial review** before it can baseline. The assistance rides *inside* the
  epistemics, never around them.
- `recurve init` auto-runs `baseline` when probes already exist (a repo whose docs
  are already checkable), collapsing init → baseline for the common case.

Highest value, highest risk — it touches `claimify` + `admission`. Sequence last.

## What we will NOT do (guardrails)

- **No "trust the agent" fast path.** The run-record + gate stay the only truth.
- **No greenwashing.** `status`/`demo` must never present green while anything is
  RED or BROKEN.
- **No removing the human from claim ownership.** Simplicity lives in the
  *ergonomics*, never the *epistemics*.
- **No silent inference.** P5 must always print what it inferred and how to override.

## Sequencing & sizing

- **Phase 1 — ergonomics, zero epistemics change:** P1 `run`, P2 `status`,
  P4 grouping, P5 zero-config init. Small→medium, low risk, biggest drop in felt
  overhead. Each gated by a new/extended suite.
- **Phase 2 — reach & polish:** P3 `demo`, P6 one-line install, P7 verification
  verbs.
- **Phase 3 — the deep one:** the design-bottleneck work (runnable scaffolds +
  gated agent-assist).

## How we verify it (dogfooding, as always)

Every new verb ships as a claims suite (probes + traps), graduated via
`recurve baseline`, enforced by `recurve gate`, and adversarially reviewed per the
capture rule. A **quickstart suite** pins the north-star bars themselves:
`recurve demo` under N seconds; `recurve run` needs no env var; default `--help`
lists ≤ K verbs. Origin-agnostic throughout.

## Open questions (human decisions)

- **Naming:** `run` vs `loop` vs `burn`? `status` vs `look`? namespaces vs a flat
  list with a curated "common" section?
- **Backward compat:** alias the old flat verbs for one release, or keep them
  indefinitely?
- **Distribution:** publish to PyPI under what name/owner; is a `curl | sh`
  installer worth maintaining?
- **Agent-assist ceiling:** how far to take `recurve draft` before it risks the
  "human owns the claims" principle?

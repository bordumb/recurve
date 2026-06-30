# Architectural invariant: separation of refereeing (actor / adversary / probe)

> Status: foundational invariant. This is not a feature — it is a rule the rest of the design obeys. It
> binds the synthesis path, the coverage gate (`completeness-layer.md`), and the stopping controller.
> Greenfield and origin-agnostic.

---

## The rule

**An actor never referees its own work. Judgment is made by the weakest-bias referee the question allows,
and any judgment that cannot be a deterministic probe must be made by an *adversary* with an opposing
incentive — whose verdict only counts once it is captured as a re-runnable probe or trap.**

Stated negatively, three things are forbidden:
- The agent that produced a change deciding whether that change is correct.
- The agent that proposed a contract deciding whether that contract is faithful.
- Any referee's verdict standing as prose ("this looks right/wrong") rather than as executable evidence.

---

## Why

An actor judging its own work has the wrong incentive (it is motivated to declare its work done and good —
sunk cost, narrative consistency, and the trained pull toward "task complete") **and** correlated failure
(the same reasoning that produced a blind spot rationalizes right past it on review). Self-refereeing is not
weak verification; it is *no* verification wearing verification's clothes — the exact "green check that
proves nothing" this whole system exists to prevent.

The fix is **not** "add a second opinion." It is to push every judgment to the lowest-bias referee that can
answer it, and to bar the actor from all of them.

---

## The referee hierarchy — use the weakest-bias referee the question allows

| Question | Referee | Bias | Notes |
|---|---|---|---|
| *Is this claim satisfied?* | a **probe** (deterministic code) | none | measurement, not judgment — the gold standard; prefer it wherever the question can be measured |
| *Should this stop / revert / pivot?* | a **controller** (deterministic; reads the gate + progress) | none | a control decision, not an opinion — never the actor |
| *Is the contract faithful? Are invariants missing? Is a probe weak?* | an **adversary** (a separate agent, opposing incentive) | toward fault-finding (useful) | irreducible judgment — *and* where self-refereeing is most corrupt; its verdict is captured (below) |

The actor appears in **none** of these rows. Measurement beats judgment whenever the question can be
measured; where it can't, an opposing-incentive adversary beats a self-interested actor — but only under the
capture rule.

---

## "Adversary," not "unbiased"

There is no unbiased agent. A second model has its own biases, and **shares the actor's** if it is the same
model on the same context — correlated failure, the worst case, because it feels like a second opinion while
being the same one. So the requirement is not neutrality; it is:

- **Opposing incentive** — the referee is rewarded for finding the flaw, not for the work being done.
- **Decorrelated failure** — different information (it sees the *output*, not the reasoning that produced
  it), and ideally a different model/prompt, so it fails in different places than the actor.
- **No shared context** between actor and referee. Sharing the actor's chain of thought re-correlates them
  and dissolves the entire benefit.

A referee biased *toward* finding fault is a feature, not a defect — it is the only bias that makes the work
better.

---

## The capture rule (this is what makes the separation real)

**An agent-referee's verdict does not count until it is expressed as a re-runnable probe or trap.** "This
looks wrong" is not an objection. The valid form of an objection is **a counterexample the work must reject**
— a trap that the *correct* implementation passes and the *wrong* one fails.

Three consequences, and they are the point:

1. **The regress bottoms out.** "Who referees the referee?" has no infinite answer in agents — it terminates
   in executable evidence (probes, traps) and, at the top, human curation. The adversary's judgment is only
   as strong as the trap it can write, and that trap then runs **forever, deterministically, without it.**
2. **Nitpicking is impossible.** A spurious objection has no discriminating counterexample — it cannot be
   expressed as a trap that distinguishes wrong from right, so it is discarded. The referee must *earn* an
   objection by producing one.
3. **A one-time biased judgment becomes permanent unbiased evidence.** The adversary's opinion is laundered
   into a probe. The bias did useful work (it *found* the hole); it does not persist in the verdict.

So the loop is: actor closes claims → adversary tries to write a surviving trap (a hole the contract
permits) → a surviving trap joins the gate as a new RED claim → actor closes it. The adversary's
fault-seeking bias is exactly what is wanted, and its output is disciplined into deterministic, re-runnable
evidence — never a standing opinion.

---

## Where this binds across the system

- **Synthesis / contract quality** (`completeness-layer.md` §2, §4): the proposer that drafts the contract,
  red-teams the claim set, and judges fidelity-to-intent **must** be the adversary — separate from whatever
  closes the claims, opposing-incentive, and its objections deposited as goal-level traps.
- **Correctness** (the gate): decided by probes. No agent referee. Already invariant in the core model.
- **Stop / revert / pivot** (the stopping controller): decided by a deterministic controller reading the
  gate and the progress vector. Never the actor, and — where it can be made deterministic — not an agent at
  all.
- **Coverage / the frontier**: a deterministic measurement, not a judgment. The adversary may *propose* that
  an uncovered point matters; that proposal counts only as a trap on that point.

---

## Honest limits

- **Cost.** A separate adversary doubles inference. Spend it only on the irreducible-judgment row; let probes
  and the controller referee the rest for free. Most refereeing in a well-formed system is measurement, and
  measurement is cheap.
- **Balance.** An adversary rewarded purely for finding fault never lets anything ship. The capture rule (a
  valid objection must be a discriminating trap) is the forcing function that disciplines it; human curation
  of the contract is the final backstop. Tune for tension, not for a winner.
- **It bottoms out in trust you choose.** The regress ends at the probes you accept and the contract a human
  curated. Separation removes *self*-refereeing and *correlated* refereeing; it does not manufacture
  ground truth from nothing. Something at the bottom is asserted — make it small, executable, and explicit.

---

**One line:** never replace a biased self-referee with a second biased agent — replace judgment with
measurement wherever you can, and where you can't, use an adversary whose only valid output is a trap. The
actor never judges its own work; the probe judges by running; the adversary judges by trying to break — and
the system keeps the break, not the opinion.

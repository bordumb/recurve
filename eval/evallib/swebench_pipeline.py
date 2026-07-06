"""swebench_pipeline.py — the SWE-bench cell pipeline, wired end to end.

A sibling to `orchestrate.py`/`run_pipeline.py`, not a fork of them: it reuses
`ArmSpec`, `DoneSignalPort`, the boundary/audit ports, the dollar-budget
watchdog, and the results-row shape UNCHANGED (docs/plans/
eval-swebench-infra.md's own bound — "SWE-bench is a new WorkspacePort/
oracle adapter pair, not a fork of the harness"). What differs is the ONE
thing that must: how a cell is graded. BigCodeBench's `make_orchestrator`
grades by reading `workspace/solution.py` through `quarantine.evaluate`
(module-level, not swappable); SWE-bench grades by extracting a diff and
running it through `swebench_quarantine.grade_fresh` in a FRESH container.
Rather than special-case that inside the shared orchestrator (forbidden —
"do not modify the kernel pipeline itself to special-case SWE-bench"), this
module is a parallel pipeline that shares everything ELSE.

`SWE_A0`/`SWE_A9` reuse `eval-arm-kernel.md`'s AK-2 insight directly: both
point `workspace` at the SAME new `"swe_bench_repo"` port (always a real,
recurve-init'd ledger — a real repo checkout the agent can run tests
against), differing only in `done_signal`/`governor` — `self_report` (the
ledger is present but never consulted, exactly A0/A6's relationship) vs
`gate` + `governor="mechanical_review"` (the ledger's own gate verdict AND a
real, decorrelated review-tier pass both decide). `SWE_A9` is `replace
(arm_spec("A9"), workspace="swe_bench_repo")` — A9 ITSELF (`ablation-infra.md`
AI2/AI6, `oracle-strength-and-decorrelation.md` R5) is reused completely
unchanged; only its `workspace` axis is repointed. One workspace adapter, per
the PRD's own singular phrasing; the 0%-vs-100%-recurve(+governor) axis is
`done_signal`/`governor`, not a second, near-duplicate workspace port.

`configure_governor`/`run_recurve_decide`/`make_governed_gate_fn` are the
piece that makes A9's governor REAL rather than merely recorded: SW6's
`gate_fn` (below) runs `recurve matrix --gate` exactly as A3 always did, AND
— only once that is green — a real `recurve decide` subprocess, with the
workspace's `[gate] governor=` configured and `RECURVE_GOVERNOR_CMD`/
`RECURVE_ACTOR_MODEL` set, so `decide_cli.verdict_for`'s live R5 wiring
(`ablation-infra.md` AI2, proven by `AB-13`) actually resolves and invokes
`MechanicalReviewGovernor` — a genuinely different model reviewing the
cycle's own commit, not a stand-in. A governor PENDING/vetoed verdict is
treated as "not yet done" (red), never silently overridden.
"""

from __future__ import annotations

import re
import subprocess
import sys
from dataclasses import asdict, replace
from pathlib import Path

from evallib.arms import ArmSpec, arm_spec, resolve_boundary_adapter
from evallib.audit import resolve_audit_port
from evallib.done_signal import resolve_done_signal_port
from evallib.swebench_majority import grade_with_majority_vote
from evallib.swebench_workspace import materialize_swe_repo_workspace

SWE_A0 = ArmSpec(workspace="swe_bench_repo", done_signal="self_report",
                  label="0% recurve (SWE-bench)")
# A9 = A3 + governor="mechanical_review" (evallib.arms, unmodified) — only
# `workspace` is repointed; `done_signal="gate"`, `governor="mechanical_review"`
# and everything else ride through exactly as A9 already defines them.
SWE_A9 = replace(arm_spec("A9"), workspace="swe_bench_repo",
                  label="100% recurve + governor=mechanical_review (SWE-bench)")
SWE_ARMS = {"A0": SWE_A0, "A9": SWE_A9}

# 2 models x 2 arms x 3 instances is SW6's whole matrix; the price table
# already prices both models (telemetry.PRICES_2026_07_04) — reused, not
# duplicated. For a governed (A9) cell, the ACTOR and the REVIEWER must be
# genuinely different models (mechanical_review's own identity-difference
# requirement) — `reviewer_model_for` picks the other one.
SWE_MODELS_DEFAULT = ("claude-haiku-4-5", "claude-sonnet-5")


def reviewer_model_for(actor_model: str, models=SWE_MODELS_DEFAULT) -> str:
    """The decorrelated reviewer: any model other than the acting one. With
    only two models configured, this is simply "the other one" — still a
    genuine identity difference, never the same model reviewing itself."""
    others = [m for m in models if m != actor_model]
    return others[0] if others else actor_model


class BudgetCeilingExceeded(RuntimeError):
    """The smoke's total real spend exceeded its ceiling — logged/halted at
    the NEXT cell boundary (there is no way to refuse a $ already billed).
    Per-cell cap is the primary control (EV-24's hard-kill watchdog is the
    real backstop); this is the coarse, whole-smoke-level trip wire."""


def expand_smoke_cells(instance_ids, models=SWE_MODELS_DEFAULT,
                        budget: float = 4.0, seed: int = 0) -> list[dict]:
    """SW6's cross product: 2 models x {SWE_A0, SWE_A9} x N instances.
    `instance_ids` is a list — SW6 runs 3 small/cheap instances, not one.
    Mirrors `plan.expand`'s cell shape (`cell_id` derived the SAME way,
    `plan.cell_id`, reused not reimplemented) plus `_arm_spec`, threaded
    explicitly because SWE_A0/SWE_A9 are local `ArmSpec` instances (SWE_A9
    built via `replace()` on the real A9), not registered names in
    `evallib.arms._ARMS`."""
    from evallib.plan import cell_id
    if isinstance(instance_ids, str):
        instance_ids = [instance_ids]
    cells = []
    for instance_id in instance_ids:
        for model in models:
            for arm_name, spec in SWE_ARMS.items():
                cells.append({
                    "cell_id": cell_id(model, f"swe-{arm_name}", budget, seed, instance_id),
                    "model": model, "arm": arm_name, "budget": budget, "seed": seed,
                    "task_id": instance_id, "_arm_spec": spec,
                })
    return cells


def assert_within_budget(rows: list[dict], ceiling_usd: float) -> float:
    """Sum the REAL billed spend (`cost_usd`, EV-23's convention — never a
    token estimate) across `rows` and raise `BudgetCeilingExceeded` if it is
    over `ceiling_usd`; otherwise return the total."""
    total = sum(float(r.get("cost_usd") or 0.0) for r in rows)
    if total > ceiling_usd:
        raise BudgetCeilingExceeded(
            f"SW6 smoke spent ${total:.4f} > ceiling ${ceiling_usd:.2f}")
    return total


_GOVERNOR_LINE_RE = re.compile(r"^\s*governor\s*=.*$", re.MULTILINE)


def configure_governor(testbed: Path, governor: str) -> None:
    """Patch `testbed`'s OWN `.recurve/recurve.toml` `[gate]` table so
    `governor=` names the requested tier — a fresh `recurve init` emits a
    `[gate]` section with NO `governor=` line at all, which resolves to the
    engine default `"mechanical"` (`core/config.py`), not `"off"`; this adds
    (or replaces) an explicit line so A9's `governor="mechanical_review"`
    is what a real `recurve decide` in this workspace actually resolves."""
    toml_path = Path(testbed) / ".recurve" / "recurve.toml"
    text = toml_path.read_text()
    line = f'governor = "{governor}"'
    if _GOVERNOR_LINE_RE.search(text):
        text = _GOVERNOR_LINE_RE.sub(line, text, count=1)
    else:
        text = text.replace("[gate]", f"[gate]\n{line}", 1)
    toml_path.write_text(text)


def commit_snapshot_for_governor(testbed: Path) -> None:
    """The governor's `build_cycle_snapshot(tree, "HEAD", ...)` reads the
    claim's files FROM the `HEAD` commit, not the working tree -- and the
    gated agent prompt never instructs the agent to commit anything (nor
    could that be relied on structurally even if it did). Left alone, `HEAD`
    is only ever `default_extract_tree`'s pre-agent commit, which predates
    `_recurve_init` -- it never contains a `.recurve/claims/` directory at
    all, so the snapshot can never resolve and the governor permanently
    reads as unreachable ("pending"), regardless of the actual fix's
    quality. The harness commits the CURRENT state itself, unconditionally,
    right before the governor is consulted -- a structural guarantee that
    does not depend on the agent's behavior. --no-gpg-sign: throwaway,
    internal bookkeeping, never a real user-authored commit."""
    subprocess.run(["git", "add", "-A"], cwd=testbed, check=True)
    subprocess.run(["git", "-c", "user.email=recurve@localhost", "-c", "user.name=recurve",
                    "commit", "--no-gpg-sign", "-q", "-m", "governor snapshot"],
                   cwd=testbed)  # no check=True: "nothing to commit" (rc=1) is a fine no-op


def run_recurve_decide(testbed: Path, *, actor_model: str, governor_cmd: str,
                        open_: int = 0, regressed: int = 0, broken: int = 0,
                        uncovered: int = 0, timeout: int = 300) -> str:  # pragma: no cover - spawns a real reviewer process
    """Run the REAL `recurve decide` CLI in `testbed`, with the governor
    genuinely wired: `RECURVE_ACTOR_MODEL` establishes the cycle's own
    claim-authoring identity, `RECURVE_GOVERNOR_CMD` names the reviewer
    command `decide_cli._resolve_governor_status` will actually invoke
    (`swebench_governor_reviewer.py`, a real second-model pass). Returns the
    printed verdict string: `STOP-SUCCESS` / `PENDING-GOVERNOR` / `CONTINUE`
    / `STOP-REVERT`."""
    import os
    env = {**os.environ, "RECURVE_ACTOR_MODEL": actor_model, "RECURVE_GOVERNOR_CMD": governor_cmd}
    r = subprocess.run(
        ["recurve", "decide", "--open", str(open_), "--regressed", str(regressed),
         "--broken", str(broken), "--uncovered", str(uncovered)],
        cwd=testbed, capture_output=True, text=True, env=env, timeout=timeout)
    return (r.stdout or "").strip()


def make_governed_gate_fn(governor: str, actor_model: str, governor_cmd: str):
    """A `gate_fn(workspace)` for `DoneSignalPort["gate"]`: `recurve matrix
    --gate` decides as always; ONLY when that is green does this ALSO run a
    real `recurve decide` with the governor configured — a governor that is
    PENDING or vetoes is "not yet done" (red), never silently overridden by
    a green conformance matrix alone. `governor="off"` (e.g. SWE_A0 is never
    routed here, but a caller composing a bare-A-family gate_fn might) skips
    the second call entirely, byte-identical to `_default_gate`."""
    def gate_fn(workspace):  # pragma: no cover - the "off" branch is hermetic; governor!="off" spawns real processes
        testbed = Path(workspace) / "testbed"
        base = _default_gate(workspace)
        if base != "green" or governor == "off":
            return base
        configure_governor(testbed, governor)
        commit_snapshot_for_governor(testbed)
        verdict = run_recurve_decide(testbed, actor_model=actor_model, governor_cmd=governor_cmd)
        if verdict == "STOP-SUCCESS":
            return "green"
        if verdict in ("PENDING-GOVERNOR", "CONTINUE"):
            return "red"   # governor didn't clear it — not genuinely done yet
        return "broken"    # STOP-REVERT or an unexpected verdict
    return gate_fn

REQUIRED_ROW_FIELDS = (
    "cell_id", "model", "arm", "task_id",
    "declared_done", "oracle_verdict",
    "dataset_revision", "recurve_commit", "adapter_version", "seed",
    "oracle_env_hash",   # here: the per-instance `environment_image_hash` (SW1/SW4)
)

SWE_BARE_PROMPT = (
    "Read TASK.md. `testbed/` is a real, working checkout of the repo "
    "described there, with its dependencies already installed. Fix the "
    "issue by editing files under testbed/. You may run "
    "`./run_tests.sh <pytest args>` to check your work against the repo's "
    "OWN (non-hidden) tests as you iterate. When you are satisfied, leave "
    "your changes in testbed/ and exit.")

SWE_GATED_PROMPT = (
    "Read TASK.md. `testbed/` is a real, working checkout of the repo "
    "described there, and this workspace is recurve-initialized. Express "
    "the task as a recurve claim: author a RED-first probe (your own test, "
    "derived only from the task statement) and at least one trap. Fix the "
    "issue by editing files under testbed/; use `./run_tests.sh` to check "
    "against the repo's own tests. Then burn the claim down until `recurve "
    "matrix --gate` is green. If you cannot make the gate green within your "
    "budget, stop and do NOT declare done.")


def row_is_complete(row: dict) -> bool:
    return all(k in row for k in REQUIRED_ROW_FIELDS)


class SequencingError(RuntimeError):
    """The agent has not terminated — refusing to extract a diff from (or
    quarantine-grade) a live workspace."""


def extract_diff(workspace: Path) -> str:
    """The ONLY thing that crosses from the agent's workspace into grading
    — never the container itself (SW3's bound). `testbed/` was git-init'd
    with the pre-agent checkout as its first commit
    (`swebench_workspace.default_extract_tree`), so this diff is exactly the
    agent's edits, nothing else."""
    testbed = Path(workspace) / "testbed"
    r = subprocess.run(["git", "diff"], cwd=testbed, capture_output=True, text=True)
    return r.stdout


def _apply_boundary_port(boundary: str) -> dict:
    resolve_boundary_adapter(boundary)
    if boundary == "enforced":
        return {}
    print(f"BOUNDARY OPEN for cell: arm boundary={boundary!r}", file=sys.stderr)
    return {"boundary": boundary}


def _default_gate(workspace: Path) -> str:
    r = subprocess.run(["recurve", "matrix", "--gate"], cwd=Path(workspace) / "testbed",
                        capture_output=True, text=True)
    return {0: "green", 1: "red"}.get(r.returncode, "broken")


def make_swebench_orchestrator(agent, instances_by_id: dict, environment_locks: dict,
                                provenance: dict, gate_fn=None, grader=None,
                                governor_cmd_resolver=None):
    """Return the adapter the runner drives, for SWE-bench cells. `agent(cell,
    workspace)` runs the model and returns at least `{terminated: bool,
    container_id: str}` (the agent's OWN container id, threaded through so
    `grade_fresh`'s reuse guard has something real to compare against).
    `environment_locks[task_id]` is SW1's lock (`{digest,
    environment_image_hash, ...}`). `grader` is injectable — defaults to
    `swebench_majority.grade_with_majority_vote` (3 independent verification
    runs, majority-vote verdict), so a fully-mocked call never imports
    docker. `gate_fn`, when given, is used for EVERY cell (the hermetic
    probe's path: full control, no real subprocesses). When `gate_fn` is
    None and a cell's arm names a real `governor` (A9), a per-cell governed
    gate_fn is built automatically (`make_governed_gate_fn`, keyed to that
    cell's own acting model + `governor_cmd_resolver(model)` as the REAL,
    decorrelated reviewer command) — so the SAME orchestrator serves A0 and
    A9 cells without the caller branching on arm identity."""
    grader = grader or grade_with_majority_vote
    governor_cmd_resolver = governor_cmd_resolver or (
        lambda model: f"python3 {Path(__file__).parent / 'swebench_governor_reviewer.py'} "
                       f"{reviewer_model_for(model)}")

    def orchestrate(cell: dict, workspace) -> dict:
        workspace = Path(workspace)
        agent_row = dict(agent(cell, workspace))
        if not agent_row.get("terminated"):
            raise SequencingError(
                "agent has not terminated — refusing to extract/grade a live workspace")

        spec = cell["_arm_spec"]  # threaded explicitly: SWE arms are not in evallib.arms._ARMS
        boundary_fields = _apply_boundary_port(spec.boundary)
        cell_gate_fn = gate_fn
        if cell_gate_fn is None and spec.governor != "off":
            cell_gate_fn = make_governed_gate_fn(
                spec.governor, cell["model"], governor_cmd_resolver(cell["model"]))

        # DoneSignalPort["self_report"] (evallib.done_signal, UNCHANGED) reads
        # `workspace/solution.py` as "the produced artifact" — true for
        # BigCodeBench (the code itself) and, here, for SWE-bench too: the
        # diff IS the produced artifact this benchmark's oracle grades. Write
        # it before the done-signal port runs so the SAME shared function
        # (not a SWE-bench-specific copy) works unmodified for both.
        instance = instances_by_id[cell["task_id"]]
        lock = environment_locks[cell["task_id"]]
        diff_text = extract_diff(workspace)
        (workspace / "solution.py").write_text(diff_text)

        done_port = resolve_done_signal_port(spec.done_signal)
        done_result = done_port(workspace, agent_row, gate_fn=cell_gate_fn or _default_gate,
                                 command=spec.external_ci_command)
        declared_done = done_result["declared_done"]
        gate_outcome = done_result["gate_outcome"]
        terminal_state = done_result["terminal_state"]

        audit_result = None
        if spec.audit != "none":
            audit_result = resolve_audit_port(spec.audit)(workspace)

        # The agent's OWN container id, so `grade_fresh`'s reuse guard has a
        # real id to compare against — read from `container.json`
        # (`swebench_workspace.materialize_swe_repo_workspace` writes it),
        # falling back to whatever the agent itself reported (hermetic tests
        # that never touch a real container).
        agent_container_id = agent_row.get("container_id")
        container_json = workspace / "container.json"
        if container_json.exists():
            import json as _json
            agent_container_id = _json.loads(container_json.read_text()).get("container_id")

        try:
            graded = grader(instance, diff_text, lock["digest"],
                             agent_container_id=agent_container_id)
            verdict = "pass" if graded["resolved"] else "fail"
        except Exception as e:
            verdict = "error"
            graded = {"resolved": False, "error": str(e)}

        row = {
            **{k: cell.get(k) for k in ("cell_id", "model", "arm", "budget", "seed", "task_id")},
            "declared_done": declared_done,
            "oracle_verdict": verdict,
            "gate_outcome": gate_outcome,
            "terminal_state": terminal_state,
            "tokens_in": agent_row.get("tokens_in", 0),
            "tokens_out": agent_row.get("tokens_out", 0),
            "cost_usd": agent_row.get("cost_usd", 0.0),
            "agent_exit": agent_row.get("agent_exit"),
            "diff": diff_text,
            **{k: provenance.get(k) for k in
               ("dataset_revision", "recurve_commit", "adapter_version")},
            "oracle_env_hash": lock["environment_image_hash"],
            **boundary_fields,
        }
        if "agreement" in graded:
            # Additive-only provenance -- a split vote (e.g. "2/3") stays
            # visible in the row rather than being smoothed into oracle_verdict
            # alone. Never required (older/injected graders may omit it).
            row["oracle_agreement"] = graded["agreement"]
            row["oracle_unanimous"] = graded["unanimous"]
        if audit_result is not None:
            row["audit"] = asdict(audit_result)
        return row
    return orchestrate


def make_swebench_pipeline_adapter(instances_by_id: dict, environment_locks: dict,
                                    provenance: dict, *, budget: float,
                                    recurve_cmd: str = "recurve",
                                    bare_agent=None, gated_agent=None, gate_fn=None,
                                    grader=None, governor_cmd_resolver=None):
    """The conductor: materialize (WorkspacePort["swe_bench_repo"], SW1's
    environment image, SW2's quarantine) -> the arm-appropriate agent ->
    `make_swebench_orchestrator` (SW3's fresh-container grading). Both
    agents injectable; a fully-mocked run never imports docker or the paid
    Claude adapter."""
    if bare_agent is None or gated_agent is None:
        from evallib.adapters.claude import make_adapter, make_gated_adapter
        bare_agent = bare_agent or make_adapter(lambda cell: SWE_BARE_PROMPT)
        gated_agent = gated_agent or make_gated_adapter(lambda cell: SWE_GATED_PROMPT, budget)

    def routed_agent(cell: dict, workspace) -> dict:
        spec = cell["_arm_spec"]
        instance = instances_by_id[cell["task_id"]]
        lock = environment_locks[cell["task_id"]]
        # Materialized directly (not through evallib.materialize.materialize):
        # SWE_A0/SWE_A3 are local ArmSpec instances, not registered names in
        # evallib.arms._ARMS, so there is no `arm_spec(cell["arm"])` lookup to
        # key a generic dispatch on. The workspace PORT itself is still the
        # one registered under "swe_bench_repo" (materialize.WORKSPACE_PORTS)
        # — called directly here for the same reason run_pipeline.py's own
        # routed_agent calls `materialize()` directly rather than duplicating
        # per-arm branches.
        materialize_swe_repo_workspace(
            Path(workspace), instance, recurve_cmd=recurve_cmd,
            environment_image_digest=lock["digest"])
        agent = gated_agent if spec.done_signal == "gate" else bare_agent
        return agent(cell, workspace)

    return make_swebench_orchestrator(routed_agent, instances_by_id, environment_locks,
                                       provenance, gate_fn=gate_fn, grader=grader,
                                       governor_cmd_resolver=governor_cmd_resolver)

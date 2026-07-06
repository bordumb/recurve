"""materialize.py — task -> fresh workspace, with the oracle quarantined.

Houses `WorkspacePort`: `"bare"` writes the task statement + an empty
solution.py into a git-init'd tmpdir; `"recurve_init"` does the same, then
also runs `recurve init`. Both stay pure materialization — no
decision-making — regardless of which done-signal or other axis the arm
built on top of that workspace uses. `materialize()` looks the arm's
`workspace` value up in `WORKSPACE_PORTS` and calls it; it never branches on
the arm's name.

Never references the task's hidden `test` field, and `assert_quarantined` is
a defense-in-depth guard that refuses any workspace in which the hidden test
text appears — the one leak that would invalidate every downstream number.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from evallib.arms import arm_spec


class QuarantineError(RuntimeError):
    """The hidden oracle leaked into an agent-visible workspace."""


def assert_quarantined(dest: str | Path, task: dict) -> None:
    """Raise QuarantineError if the task's hidden `test` text appears in any file
    under `dest`. A no-op on a clean workspace; the last line of defense against
    an agent ever seeing the oracle it is graded by."""
    hidden = (task.get("test") or "").strip()
    if not hidden:
        return
    for p in Path(dest).rglob("*"):
        if p.is_file():
            try:
                if hidden in p.read_text(errors="ignore"):
                    raise QuarantineError(
                        f"hidden test leaked into {p} — the oracle must never "
                        f"enter an agent workspace")
            except (UnicodeDecodeError, OSError):
                continue


def _write_task(dest: Path, task: dict) -> None:
    """The materialization every workspace port shares: task statement, an
    empty solution.py, and a git-init'd tree."""
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "TASK.md").write_text(
        f"# Task {task.get('task_id', '')}\n\n{task.get('instruct_prompt', '')}\n")
    (dest / "solution.py").write_text("")
    subprocess.run(["git", "init", "-q"], cwd=dest, check=True)


def bare_workspace(dest: Path, task: dict, *, recurve_cmd: str | None = None) -> None:
    """WorkspacePort["bare"] — task + empty solution.py, git-init'd; no recurve
    anywhere in the tree (A0)."""
    _write_task(dest, task)


def recurve_init_workspace(dest: Path, task: dict, *, recurve_cmd: str | None = None) -> None:
    """WorkspacePort["recurve_init"] — the same materialization, then
    `recurve init` (A3 and everything built on it: a real ledger is present,
    but which done-signal reads it is a separate, independent axis)."""
    _write_task(dest, task)
    cmd = recurve_cmd or "recurve"
    subprocess.run([cmd if cmd == "recurve" else "python3", *([] if cmd == "recurve" else [cmd]),
                    "init"], cwd=dest,
                   capture_output=True, text=True)


def _swe_bench_repo_workspace(dest: Path, task: dict, *, recurve_cmd: str | None = None) -> None:
    """WorkspacePort["swe_bench_repo"] — a thin registry adapter over
    `swebench_workspace.materialize_swe_repo_workspace` (docs/plans/
    eval-swebench-infra.md SW2): a real, working container checkout, but
    structurally missing test_patch. Lives in its own module (a different
    task shape entirely — a repo, not a function) and is wired in here as
    ONE registry line, exactly the property `eval-arm-kernel.md` requires:
    adding a WorkspacePort value never touches this dispatcher."""
    from evallib.swebench_workspace import materialize_swe_repo_workspace
    materialize_swe_repo_workspace(dest, task, recurve_cmd=recurve_cmd)


WORKSPACE_PORTS = {
    "bare": bare_workspace,
    "recurve_init": recurve_init_workspace,
    "swe_bench_repo": _swe_bench_repo_workspace,
}


def resolve_workspace_port(name: str):
    if name not in WORKSPACE_PORTS:
        raise KeyError(f"unknown workspace {name!r}; known: {', '.join(WORKSPACE_PORTS)}")
    return WORKSPACE_PORTS[name]


def materialize(task: dict, arm: str, dest: str | Path,
                recurve_cmd: str | None = None) -> Path:
    """Build a fresh workspace for one (task, arm) cell and return its path.

    Looks up `arm`'s `workspace` value in `WORKSPACE_PORTS` and calls it —
    never branches on the arm's name or any other property.
    `assert_quarantined` re-checks the built workspace before returning."""
    spec = arm_spec(arm)
    dest = Path(dest)
    resolve_workspace_port(spec.workspace)(dest, task, recurve_cmd=recurve_cmd)
    assert_quarantined(dest, task)
    return dest
